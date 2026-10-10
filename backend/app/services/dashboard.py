"""Executive dashboard aggregation. Every number is derived from stored records."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import Perm
from app.models import AuditLog, Dataset, Finding, FindingStatus, ImportJob, KpiValue
from app.services.context import RequestContext
from app.services.findings import PRIORITY_ORDER
from app.services.kpi_service import latest_runs, latest_totals
from app.services.organizations import org_setting

OPEN_STATUSES = (FindingStatus.OPEN, FindingStatus.IN_REVIEW, FindingStatus.ACTION_PLANNED)


def build(db: Session, ctx: RequestContext, *, area: str | None = None, dataset_id: int | None = None,
          include_demo: bool = True) -> dict:
    ds_stmt = select(Dataset).where(Dataset.organization_id == ctx.org_id)
    if not include_demo:
        ds_stmt = ds_stmt.where(Dataset.is_demo.is_(False))
    datasets = list(db.execute(ds_stmt.order_by(Dataset.created_at.desc())).scalars())

    f_stmt = select(Finding).where(Finding.organization_id == ctx.org_id, Finding.status.in_(OPEN_STATUSES))
    if area:
        f_stmt = f_stmt.where(Finding.area == area)
    if dataset_id:
        f_stmt = f_stmt.where(Finding.dataset_id == dataset_id)
    if not include_demo:
        f_stmt = f_stmt.where(Finding.is_demo.is_(False))
    open_findings = list(db.execute(f_stmt.order_by(PRIORITY_ORDER, Finding.last_detected_at.desc())).scalars())

    by_priority: dict[str, int] = {}
    by_area: dict[str, int] = {}
    by_nature: dict[str, int] = {}
    impact_by_nature: dict[str, float] = {}
    for f in open_findings:
        by_priority[f.priority] = by_priority.get(f.priority, 0) + 1
        by_area[f.area] = by_area.get(f.area, 0) + 1
        by_nature[f.nature] = by_nature.get(f.nature, 0) + 1
        if f.impact_amount and f.condition_active:
            impact_by_nature[f.nature] = round(impact_by_nature.get(f.nature, 0.0) + f.impact_amount, 2)

    kpis = latest_totals(db, ctx, include_demo, dataset_id)
    if area:
        kpis = [k for k in kpis if k["area"] == area]

    runs = latest_runs(db, ctx, include_demo, dataset_id)
    series = []
    if runs:
        monthly = db.execute(
            select(KpiValue).where(
                KpiValue.organization_id == ctx.org_id,
                KpiValue.analysis_run_id.in_([r.id for r in runs.values()]),
                KpiValue.granularity == "month",
                KpiValue.status == "ok",
            ).order_by(KpiValue.kpi_code, KpiValue.period_start)
        ).scalars()
        grouped: dict[tuple[str, int], list] = {}
        for v in monthly:
            grouped.setdefault((v.kpi_code, v.dataset_id), []).append({"period": v.period_start, "value": v.value})
        names = {k["kpi_code"]: k for k in kpis}
        for (code, ds_id), points in grouped.items():
            if code in names and len(points) >= 2:
                series.append({"kpi_code": code, "name": names[code]["name"], "unit": names[code]["unit"],
                               "dataset_id": ds_id, "dataset_name": runs[ds_id].dataset.name, "points": points})

    recent_imports = list(
        db.execute(
            select(ImportJob).where(ImportJob.organization_id == ctx.org_id).order_by(ImportJob.id.desc()).limit(5)
        ).scalars()
    )
    activity = []
    if ctx.has(Perm.AUDIT_READ):
        activity = [
            {"id": a.id, "action": a.action, "actor": a.actor_label, "entity_type": a.entity_type, "entity_id": a.entity_id,
             "created_at": a.created_at}
            for a in db.execute(
                select(AuditLog).where(AuditLog.organization_id == ctx.org_id).order_by(AuditLog.id.desc()).limit(10)
            ).scalars()
        ]
    total_records = sum(d.row_count for d in datasets)
    resolved_count = db.scalar(
        select(func.count()).select_from(Finding).where(Finding.organization_id == ctx.org_id,
                                                         Finding.status == FindingStatus.RESOLVED)
    )
    return {
        "has_data": bool(datasets),
        "has_demo_data": bool(db.scalar(
            select(func.count()).select_from(Dataset).where(Dataset.organization_id == ctx.org_id, Dataset.is_demo.is_(True))
        )),
        "currency": org_setting(ctx.org, "currency"),
        "datasets": [
            {"id": d.id, "name": d.name, "template_code": d.template_code, "row_count": d.row_count, "is_demo": d.is_demo,
             "last_analyzed_at": d.last_analyzed_at, "analysis_stale": d.analysis_stale}
            for d in datasets
        ],
        "total_records": total_records,
        "findings": {
            "open_total": len(open_findings),
            "resolved_total": int(resolved_count or 0),
            "by_priority": by_priority,
            "by_area": by_area,
            "by_nature": by_nature,
            "top": [
                {"id": f.id, "code": f.code, "title": f.title, "priority": f.priority, "area": f.area, "nature": f.nature,
                 "status": f.status, "impact_amount": f.impact_amount, "impact_currency": f.impact_currency,
                 "is_demo": f.is_demo, "condition_active": f.condition_active}
                for f in open_findings[:8]
            ],
        },
        "impact": {
            "open_estimated_by_nature": impact_by_nature,
            "note": "Impacto estimado de hallazgos abiertos con condición vigente. No representa ahorros realizados.",
        },
        "kpis": kpis,
        "series": series,
        "recent_imports": [
            {"id": j.id, "filename": j.original_filename, "status": j.status, "created_at": j.created_at,
             "imported_rows": j.imported_rows, "is_demo": j.is_demo}
            for j in recent_imports
        ],
        "activity": activity,
    }
