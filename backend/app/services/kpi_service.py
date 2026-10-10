"""KPI catalog with organization targets and computed values."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.models import AnalysisRun, Dataset, KpiTarget, KpiValue
from app.services import audit
from app.services.analytics.kpis import CATALOG, KPIS
from app.services.context import RequestContext
from app.services.tenancy import get_owned


def latest_runs(db: Session, ctx: RequestContext, include_demo: bool = True, dataset_id: int | None = None) -> dict[int, AnalysisRun]:
    stmt = (
        select(AnalysisRun)
        .join(Dataset, Dataset.id == AnalysisRun.dataset_id)
        .where(AnalysisRun.organization_id == ctx.org_id, AnalysisRun.status == "completed")
        .order_by(AnalysisRun.id)
    )
    if not include_demo:
        stmt = stmt.where(Dataset.is_demo.is_(False))
    if dataset_id:
        stmt = stmt.where(AnalysisRun.dataset_id == dataset_id)
    runs: dict[int, AnalysisRun] = {}
    for run in db.execute(stmt).scalars():
        runs[run.dataset_id] = run  # last one wins
    return runs


def targets(db: Session, ctx: RequestContext) -> dict[str, KpiTarget]:
    return {t.kpi_code: t for t in db.execute(select(KpiTarget).where(KpiTarget.organization_id == ctx.org_id)).scalars()}


def evaluate(kpi_code: str, value: float | None, target: KpiTarget | None) -> str | None:
    """Return 'meets' | 'misses' | None (no target or no value)."""
    if target is None or value is None:
        return None
    kpi = KPIS[kpi_code]
    tol = target.tolerance or 0
    if kpi.direction == "higher_is_better":
        return "meets" if value >= target.target_value - tol else "misses"
    if kpi.direction == "lower_is_better":
        return "meets" if value <= target.target_value + tol else "misses"
    return None


def latest_totals(db: Session, ctx: RequestContext, include_demo: bool = True, dataset_id: int | None = None) -> list[dict]:
    runs = latest_runs(db, ctx, include_demo, dataset_id)
    if not runs:
        return []
    tg = targets(db, ctx)
    values = db.execute(
        select(KpiValue).where(
            KpiValue.organization_id == ctx.org_id,
            KpiValue.analysis_run_id.in_([r.id for r in runs.values()]),
            KpiValue.granularity == "total",
            KpiValue.dimension.is_(None),
        )
    ).scalars()
    out = []
    for v in values:
        run = runs[v.dataset_id]
        target = tg.get(v.kpi_code)
        out.append({
            "kpi_code": v.kpi_code, "name": KPIS[v.kpi_code].name, "area": KPIS[v.kpi_code].area,
            "unit": KPIS[v.kpi_code].unit, "direction": KPIS[v.kpi_code].direction,
            "dataset_id": v.dataset_id, "dataset_name": run.dataset.name, "is_demo": run.dataset.is_demo,
            "analysis_run_id": run.id, "computed_at": v.computed_at, "period_start": run.period_start,
            "period_end": run.period_end, "value": v.value, "status": v.status, "sample_size": v.sample_size,
            "inputs": v.inputs, "message": v.message,
            "target": target.target_value if target else None, "evaluation": evaluate(v.kpi_code, v.value, target),
        })
    order = {k.code: i for i, k in enumerate(CATALOG)}
    out.sort(key=lambda r: (order.get(r["kpi_code"], 999), r["dataset_name"]))
    return out


def kpi_detail(db: Session, ctx: RequestContext, kpi_code: str, dataset_id: int) -> dict:
    if kpi_code not in KPIS:
        raise NotFound("Indicador no encontrado.")
    dataset = get_owned(db, Dataset, dataset_id, ctx, "Conjunto de datos")
    runs = latest_runs(db, ctx, dataset_id=dataset.id)
    run = runs.get(dataset.id)
    kpi = KPIS[kpi_code]
    target = targets(db, ctx).get(kpi_code)
    result = {"definition": kpi.public(), "dataset": {"id": dataset.id, "name": dataset.name, "is_demo": dataset.is_demo},
              "target": _target_dict(target), "analysis_run_id": run.id if run else None,
              "total": None, "by_dimension": [], "monthly": [], "history": []}
    if run is None:
        return result
    rows = db.execute(
        select(KpiValue).where(KpiValue.analysis_run_id == run.id, KpiValue.kpi_code == kpi_code,
                               KpiValue.organization_id == ctx.org_id)
    ).scalars()
    for v in rows:
        item = {"value": v.value, "status": v.status, "sample_size": v.sample_size, "inputs": v.inputs, "message": v.message,
                "evaluation": evaluate(kpi_code, v.value, target)}
        if v.granularity == "month":
            result["monthly"].append({"period_start": v.period_start, "period_end": v.period_end, **item})
        elif v.dimension:
            result["by_dimension"].append({"dimension_value": v.dimension_value, **item})
        else:
            result["total"] = item
    result["monthly"].sort(key=lambda r: r["period_start"])
    history = db.execute(
        select(KpiValue, AnalysisRun.finished_at)
        .join(AnalysisRun, AnalysisRun.id == KpiValue.analysis_run_id)
        .where(KpiValue.organization_id == ctx.org_id, KpiValue.dataset_id == dataset.id, KpiValue.kpi_code == kpi_code,
               KpiValue.granularity == "total", KpiValue.dimension.is_(None))
        .order_by(KpiValue.id.desc()).limit(50)
    ).all()
    result["history"] = [{"analysis_run_id": v.analysis_run_id, "computed_at": finished, "value": v.value, "status": v.status,
                          "sample_size": v.sample_size} for v, finished in history]
    return result


def _target_dict(t: KpiTarget | None) -> dict | None:
    if t is None:
        return None
    return {"target_value": t.target_value, "tolerance": t.tolerance, "owner_label": t.owner_label, "notes": t.notes,
            "updated_at": t.updated_at}


def set_target(db: Session, ctx: RequestContext, kpi_code: str, target_value: float, tolerance: float,
               owner_label: str | None, notes: str | None) -> KpiTarget:
    if kpi_code not in KPIS:
        raise NotFound("Indicador no encontrado.")
    if KPIS[kpi_code].direction == "neutral":
        raise ValidationFailed("Este indicador es informativo y no admite objetivo.")
    if tolerance < 0:
        raise ValidationFailed("La tolerancia no puede ser negativa.", details=[{"field": "tolerance", "message": "Debe ser ≥ 0."}])
    target = targets(db, ctx).get(kpi_code)
    before = _target_dict(target)
    if target is None:
        target = KpiTarget(organization_id=ctx.org_id, kpi_code=kpi_code, target_value=target_value)
        db.add(target)
    target.target_value, target.tolerance = target_value, tolerance
    target.owner_label, target.notes, target.updated_by_id = owner_label, notes, ctx.user_id
    _mark_stale(db, ctx, kpi_code)
    audit.record(db, ctx, "kpi.target_set", entity_type="kpi", entity_id=kpi_code,
                 details={"before": {k: before[k] for k in ("target_value", "tolerance")} if before else None,
                          "after": {"target_value": target_value, "tolerance": tolerance}})
    db.commit()
    return target


def delete_target(db: Session, ctx: RequestContext, kpi_code: str) -> None:
    target = targets(db, ctx).get(kpi_code)
    if target is None:
        raise NotFound("El indicador no tiene objetivo configurado.")
    db.delete(target)
    _mark_stale(db, ctx, kpi_code)
    audit.record(db, ctx, "kpi.target_deleted", entity_type="kpi", entity_id=kpi_code,
                 details={"target_value": target.target_value})
    db.commit()


def _mark_stale(db: Session, ctx: RequestContext, kpi_code: str) -> None:
    for ds in db.execute(select(Dataset).where(Dataset.organization_id == ctx.org_id,
                                                Dataset.template_code == KPIS[kpi_code].template)).scalars():
        ds.analysis_stale = True
