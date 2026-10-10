"""Collects the content of a report from stored data (no free-form generation)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.models import Dataset, Finding, FindingStatus, ImportJob, ImportStatus, Membership, User
from app.services.analytics.kpis import KPIS
from app.services.context import RequestContext
from app.services.findings import PRIORITY_ORDER
from app.services.kpi_service import latest_runs, latest_totals
from app.services.organizations import org_setting

REPORT_TYPES = {
    "diagnostic": ("Diagnóstico operativo general", None),
    "executive": ("Informe ejecutivo", None),
    "inventory": ("Reporte de inventarios", "inventory"),
    "maintenance": ("Reporte de mantenimiento", "maintenance"),
    "logistics": ("Reporte logístico", "logistics"),
    "production": ("Reporte de producción", "production"),
}
OPEN = (FindingStatus.OPEN, FindingStatus.IN_REVIEW, FindingStatus.ACTION_PLANNED)
PRIORITY_LABELS = {"critical": "Crítica", "high": "Alta", "medium": "Media", "low": "Baja"}
NATURE_LABELS = {"confirmed_issue": "Problema confirmado en datos", "statistical_anomaly": "Anomalía estadística",
                 "hypothesis": "Hipótesis a investigar"}
STATUS_LABELS = {"open": "Abierto", "in_review": "En revisión", "action_planned": "Acción planificada",
                 "resolved": "Resuelto", "dismissed": "Descartado"}


def build_report_data(db: Session, ctx: RequestContext, report_type: str, dataset_ids: list[int] | None,
                      include_demo: bool) -> dict:
    if report_type not in REPORT_TYPES:
        raise ValidationFailed("Tipo de reporte no válido.", details=[{"field": "report_type", "message": "Desconocido."}])
    title, area = REPORT_TYPES[report_type]
    ds_stmt = select(Dataset).where(Dataset.organization_id == ctx.org_id)
    if dataset_ids:
        ds_stmt = ds_stmt.where(Dataset.id.in_(dataset_ids))
    if not include_demo:
        ds_stmt = ds_stmt.where(Dataset.is_demo.is_(False))
    datasets = [d for d in db.execute(ds_stmt.order_by(Dataset.id)).scalars()
                if area is None or KPIS_BY_TEMPLATE_AREA.get(d.template_code) == area]
    if not datasets:
        raise ValidationFailed("No hay conjuntos de datos que correspondan a este reporte. Importa datos primero.",
                               code="no_data_for_report")
    ids = {d.id for d in datasets}
    runs = {k: v for k, v in latest_runs(db, ctx, include_demo).items() if k in ids}

    kpis = [k for k in latest_totals(db, ctx, include_demo) if k["dataset_id"] in ids]
    for k in kpis:
        k["formula"] = KPIS[k["kpi_code"]].formula

    findings = list(db.execute(
        select(Finding).where(Finding.organization_id == ctx.org_id, Finding.dataset_id.in_(ids))
        .order_by(PRIORITY_ORDER, Finding.id)
    ).scalars())
    owners = {u.id: u.display_name for u in db.execute(
        select(User).join(Membership, Membership.user_id == User.id).where(Membership.organization_id == ctx.org_id)
    ).scalars()}

    sources = []
    for d in datasets:
        jobs = db.execute(select(ImportJob).where(ImportJob.organization_id == ctx.org_id, ImportJob.target_dataset_id == d.id,
                                                  ImportJob.status == ImportStatus.COMMITTED)).scalars()
        run = runs.get(d.id)
        sources.append({
            "dataset": d.name, "template": d.template_code, "rows": d.row_count, "is_demo": d.is_demo,
            "analysis_run_id": run.id if run else None,
            "analyzed_at": run.finished_at.isoformat(timespec="minutes") if run and run.finished_at else None,
            "period": f"{run.period_start} a {run.period_end}" if run and run.period_start else "Sin fechas",
            "stale": d.analysis_stale,
            "files": [{"filename": j.original_filename, "sha256": j.file_sha256[:16], "rows": j.imported_rows,
                       "committed_at": j.committed_at.isoformat(timespec="minutes") if j.committed_at else None} for j in jobs],
        })

    periods = [(r.period_start, r.period_end) for r in runs.values() if r.period_start]
    period = f"{min(p[0] for p in periods)} a {max(p[1] for p in periods)}" if periods else "Sin fechas en los datos"

    limitations = []
    if any(d.is_demo for d in datasets):
        limitations.append("Incluye DATOS DE DEMOSTRACIÓN sintéticos que no pertenecen a la organización.")
    for k in kpis:
        if k["status"] != "ok":
            limitations.append(f"{k['name']} ({k['dataset_name']}): no calculado — {k['message']}")
    for s in sources:
        if s["stale"]:
            limitations.append(f"«{s['dataset']}» cambió después de su último análisis; vuelva a analizarlo para actualizar resultados.")
        if s["analysis_run_id"] is None:
            limitations.append(f"«{s['dataset']}» no ha sido analizado.")
    limitations.append("Los hallazgos estadísticos e hipótesis requieren verificación en campo antes de actuar.")
    limitations.append("Los impactos económicos son estimaciones con la base de cálculo indicada; no son ahorros realizados.")

    open_findings = [f for f in findings if f.status in OPEN]
    return {
        "title": title,
        "report_type": report_type,
        "organization": ctx.org.name,
        "currency": org_setting(ctx.org, "currency"),
        "generated_at": datetime.now(UTC).isoformat(timespec="minutes"),
        "generated_by": ctx.user.display_name if ctx.user else "sistema",
        "period": period,
        "sources": sources,
        "kpis": kpis,
        "findings": [_finding_dict(f, owners) for f in (open_findings if report_type == "executive" else findings)],
        "pending_actions": [_finding_dict(f, owners) for f in open_findings if f.condition_active],
        "summary": {
            "open_findings": len(open_findings),
            "critical_or_high": sum(1 for f in open_findings if f.priority in ("critical", "high")),
            "estimated_impact_open": round(sum(f.impact_amount or 0 for f in open_findings if f.condition_active), 2),
            "kpis_ok": sum(1 for k in kpis if k["status"] == "ok"),
            "kpis_insufficient": sum(1 for k in kpis if k["status"] != "ok"),
            "kpis_missing_target": sum(1 for k in kpis if k["status"] == "ok" and k["evaluation"] == "misses"),
        },
        "limitations": limitations,
        "is_demo": any(d.is_demo for d in datasets),
    }


def _finding_dict(f: Finding, owners: dict[int, str]) -> dict:
    return {
        "code": f.code, "title": f.title, "area": f.area, "nature": NATURE_LABELS.get(f.nature, f.nature),
        "priority": PRIORITY_LABELS.get(f.priority, f.priority), "status": STATUS_LABELS.get(f.status, f.status),
        "description": f.description, "method": f.method, "recommendation": f.recommendation,
        "impact_amount": f.impact_amount, "impact_currency": f.impact_currency, "impact_basis": f.impact_basis,
        "confidence": f.confidence, "owner": owners.get(f.owner_user_id) if f.owner_user_id else None,
        "due_date": f.due_date.isoformat() if f.due_date else None, "condition_active": f.condition_active,
        "detected_at": f.first_detected_at.date().isoformat(), "evidence_summary": _evidence_summary(f.evidence),
        "is_demo": f.is_demo,
    }


def _evidence_summary(evidence: dict) -> str:
    parts = []
    for key, value in (evidence or {}).items():
        if isinstance(value, list):
            parts.append(f"{key}: {len(value)} registros")
        elif isinstance(value, dict):
            continue
        else:
            parts.append(f"{key}: {value}")
    return "; ".join(parts)[:400]


KPIS_BY_TEMPLATE_AREA = {
    "production_records": "production", "maintenance_events": "maintenance",
    "inventory_items": "inventory", "fuel_logs": "logistics", "generic": "general",
}
