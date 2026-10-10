"""Analysis engine: dataset → profile → KPIs → rules → findings.

The engine is deterministic: the same records, settings and targets always
produce the same KPI values and findings. Each run is stored as an
``AnalysisRun`` with its data profile, and every KPI value and finding points
back to the run and dataset (traceability to the source import and rows).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AnalysisRun,
    Counter,
    Dataset,
    DatasetRecord,
    Finding,
    FindingEvent,
    FindingStatus,
    ImportJob,
    ImportStatus,
    KpiTarget,
    KpiValue,
)
from app.services import audit
from app.services.analytics import profiling
from app.services.analytics.domain import fleet, inventory, maintenance, production
from app.services.analytics.frames import records_frame
from app.services.analytics.kpis import KPIS, KpiDefinition, kpis_for_template
from app.services.analytics.rules import FindingDraft, KpiOutcome, RuleContext, run_rules
from app.services.context import RequestContext
from app.services.imports.templates import get_template
from app.services.organizations import DEFAULT_ORG_SETTINGS

log = logging.getLogger("app.analysis")

PREPARERS = {
    "production_records": production.prepare,
    "maintenance_events": maintenance.prepare,
    "inventory_items": inventory.prepare,
    "fuel_logs": fleet.prepare,
}

MAX_DIMENSION_VALUES = 100


def next_code(db: Session, org_id: int, name: str, prefix: str) -> str:
    counter = db.execute(
        select(Counter).where(Counter.organization_id == org_id, Counter.name == name).with_for_update()
    ).scalar_one_or_none()
    if counter is None:
        counter = Counter(organization_id=org_id, name=name, value=0)
        db.add(counter)
        db.flush()
    counter.value += 1
    return f"{prefix}-{counter.value:06d}"


def load_frame(db: Session, dataset: Dataset) -> pd.DataFrame:
    template = get_template(dataset.template_code)
    rows = db.execute(
        select(DatasetRecord.id, DatasetRecord.source_row, DatasetRecord.data)
        .where(DatasetRecord.dataset_id == dataset.id, DatasetRecord.organization_id == dataset.organization_id)
        .order_by(DatasetRecord.id)
    ).all()
    return records_frame(rows, template)


def prepared_frame(db: Session, dataset: Dataset, settings: dict) -> pd.DataFrame:
    df = load_frame(db, dataset)
    prep = PREPARERS.get(dataset.template_code)
    return prep(df, settings) if prep and len(df) else df


def mapped_fields_of(db: Session, dataset: Dataset) -> set[str]:
    mappings = db.execute(
        select(ImportJob.column_mapping).where(
            ImportJob.target_dataset_id == dataset.id, ImportJob.status == ImportStatus.COMMITTED
        )
    ).scalars()
    fields: set[str] = set()
    for m in mappings:
        fields |= set((m or {}).keys())
    return fields


def _compute_kpi(kpi: KpiDefinition, df: pd.DataFrame) -> KpiOutcome:
    total = kpi.compute(df)
    by_dim = {}
    if kpi.dimension and kpi.dimension in df and len(df):
        values = df[kpi.dimension].dropna().astype(str)
        for value in sorted(values.unique())[:MAX_DIMENSION_VALUES]:
            by_dim[value] = kpi.compute(df[df[kpi.dimension].astype(str) == value])
    monthly = []
    if kpi.monthly and "_month" in df and df["_month"].notna().any():
        for month in sorted(df["_month"].dropna().unique()):
            monthly.append((month, kpi.compute(df[df["_month"] == month])))
    return KpiOutcome(total, by_dim, monthly)


def _month_end(month) -> object:
    return (pd.Timestamp(month) + pd.offsets.MonthEnd(0)).date()


def run_analysis(db: Session, ctx: RequestContext, dataset: Dataset, trigger: str = "manual") -> AnalysisRun:
    template = get_template(dataset.template_code)
    settings = {**DEFAULT_ORG_SETTINGS, **(ctx.org.settings or {})}
    run = AnalysisRun(
        organization_id=ctx.org_id, dataset_id=dataset.id, triggered_by_id=ctx.user_id,
        trigger=trigger, status="running",
    )
    db.add(run)
    db.flush()
    try:
        df = prepared_frame(db, dataset, settings)
        mapped = mapped_fields_of(db, dataset)
        profile = profiling.profile(df, template, mapped or None)
        duplicates = _duplicate_records(db, dataset)

        outcomes: dict[str, KpiOutcome] = {}
        if len(df):
            for kpi in kpis_for_template(dataset.template_code):
                outcomes[kpi.code] = _compute_kpi(kpi, df)
        date_range = profile.get("date_range")
        _store_kpis(db, ctx, run, dataset, outcomes)

        targets = {t.kpi_code: t for t in db.execute(select(KpiTarget).where(KpiTarget.organization_id == ctx.org_id)).scalars()}
        drafts: list[FindingDraft] = []
        if len(df):
            rule_ctx = RuleContext(
                dataset_id=dataset.id, dataset_name=dataset.name, template=template, df=df, kpis=outcomes,
                targets=targets, settings=settings, currency=settings.get("currency", "MXN"), profile=profile,
                duplicate_records=duplicates,
            )
            drafts = run_rules(rule_ctx)
        stats = _upsert_findings(db, ctx, run, dataset, drafts, settings.get("currency", "MXN"))

        now = datetime.now(UTC)
        run.status = "completed"
        run.finished_at = now
        run.record_count = len(df)
        run.data_profile = profile
        if date_range:
            run.period_start = datetime.fromisoformat(date_range["from"]).date()
            run.period_end = datetime.fromisoformat(date_range["to"]).date()
        run.summary = {
            "kpis_computed": sum(1 for o in outcomes.values() if o.total.status == "ok"),
            "kpis_insufficient": sum(1 for o in outcomes.values() if o.total.status != "ok"),
            **stats,
        }
        dataset.last_analyzed_at = now
        dataset.analysis_stale = False
        audit.record(db, ctx, "analysis.completed", entity_type="dataset", entity_id=dataset.id,
                     details={"analysis_run_id": run.id, "trigger": trigger, **run.summary})
        db.commit()
        return run
    except Exception as exc:
        db.rollback()
        log.exception("analysis_failed", extra={"dataset_id": dataset.id})
        failed = AnalysisRun(
            organization_id=ctx.org_id, dataset_id=dataset.id, triggered_by_id=ctx.user_id, trigger=trigger,
            status="failed", finished_at=datetime.now(UTC), error_message=f"{type(exc).__name__}: {exc}"[:2000],
        )
        db.add(failed)
        audit.record(db, ctx, "analysis.failed", entity_type="dataset", entity_id=dataset.id,
                     details={"error": type(exc).__name__})
        db.commit()
        return failed


def _duplicate_records(db: Session, dataset: Dataset) -> int:
    sub = (
        select(DatasetRecord.fingerprint, func.count().label("n"))
        .where(DatasetRecord.dataset_id == dataset.id)
        .group_by(DatasetRecord.fingerprint)
        .having(func.count() > 1)
        .subquery()
    )
    return int(db.scalar(select(func.coalesce(func.sum(sub.c.n - 1), 0))) or 0)


def _store_kpis(db: Session, ctx: RequestContext, run: AnalysisRun, dataset: Dataset, outcomes: dict[str, KpiOutcome]) -> None:
    rows = []

    def add(code, granularity, result, dimension=None, dimension_value=None, start=None, end=None):
        rows.append(KpiValue(
            organization_id=ctx.org_id, analysis_run_id=run.id, dataset_id=dataset.id, kpi_code=code,
            granularity=granularity, dimension=dimension, dimension_value=dimension_value,
            period_start=start, period_end=end, value=result.value, status=result.status,
            sample_size=result.sample_size, inputs=result.inputs, message=result.message,
        ))

    for code, outcome in outcomes.items():
        add(code, "total", outcome.total)
        for value, result in outcome.by_dimension.items():
            add(code, "total", result, KPIS[code].dimension, value)
        for month, result in outcome.monthly:
            add(code, "month", result, start=month, end=_month_end(month))
    db.add_all(rows)


def _upsert_findings(
    db: Session, ctx: RequestContext, run: AnalysisRun, dataset: Dataset, drafts: list[FindingDraft], currency: str
) -> dict:
    now = datetime.now(UTC)
    existing = {
        f.fingerprint: f
        for f in db.execute(
            select(Finding).where(Finding.organization_id == ctx.org_id, Finding.dataset_id == dataset.id)
        ).scalars()
    }
    created = updated = reopened = cleared = 0
    detected: set[str] = set()
    for draft in drafts:
        fp = draft.fingerprint(dataset.id)
        if fp in detected:
            continue
        detected.add(fp)
        fields = dict(
            area=draft.area, category=draft.category, nature=draft.nature, title=draft.title[:300],
            description=draft.description, evidence=draft.evidence, rule_code=draft.rule_code, method=draft.method,
            priority=draft.priority, impact_amount=draft.impact_amount,
            impact_currency=currency if draft.impact_amount is not None else None, impact_basis=draft.impact_basis,
            impact_kind=draft.impact_kind if draft.impact_amount is not None else None,
            confidence=draft.confidence, confidence_basis=draft.confidence_basis, recommendation=draft.recommendation,
        )
        finding = existing.get(fp)
        if finding is None:
            finding = Finding(
                organization_id=ctx.org_id, code=next_code(db, ctx.org_id, "finding", "HAL"), fingerprint=fp,
                dataset_id=dataset.id, status=FindingStatus.OPEN, first_detected_at=now, last_detected_at=now,
                last_analysis_run_id=run.id, is_demo=dataset.is_demo, **fields,
            )
            db.add(finding)
            db.flush()
            _event(db, ctx, finding, "detected", note="Detectado por el análisis.", data={"analysis_run_id": run.id})
            created += 1
            continue
        for key, value in fields.items():
            setattr(finding, key, value)
        finding.last_detected_at = now
        finding.last_analysis_run_id = run.id
        if not finding.condition_active:
            finding.condition_active = True
            _event(db, ctx, finding, "condition_detected_again", note="La condición vuelve a detectarse.", data={"analysis_run_id": run.id})
        if finding.status == FindingStatus.RESOLVED:
            _event(db, ctx, finding, "reopened_by_analysis", from_status=finding.status, to_status=FindingStatus.OPEN,
                   note="Se marcó como resuelto pero la condición persiste en los datos.", data={"analysis_run_id": run.id})
            finding.status = FindingStatus.OPEN
            reopened += 1
        updated += 1
    for fp, finding in existing.items():
        if fp not in detected and finding.condition_active:
            finding.condition_active = False
            finding.last_analysis_run_id = run.id
            _event(db, ctx, finding, "condition_not_detected",
                   note="El análisis más reciente ya no detecta la condición con los datos disponibles.",
                   data={"analysis_run_id": run.id})
            cleared += 1
    return {"findings_created": created, "findings_updated": updated, "findings_reopened": reopened,
            "findings_no_longer_detected": cleared, "findings_detected": len(detected)}


def _event(db: Session, ctx: RequestContext, finding: Finding, event_type: str, *, note: str | None = None,
           from_status: str | None = None, to_status: str | None = None, data: dict | None = None) -> None:
    db.add(FindingEvent(
        organization_id=finding.organization_id, finding_id=finding.id, actor_user_id=ctx.user_id,
        actor_label="análisis automático" if event_type != "status_changed" else ctx.actor_label,
        event_type=event_type, from_status=from_status, to_status=to_status, note=note, data=data or {},
    ))
