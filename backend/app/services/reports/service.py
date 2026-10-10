from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.models import Report
from app.services import audit, storage
from app.services.context import RequestContext
from app.services.reports.builder import build_report_data
from app.services.reports.render import render_pdf, render_xlsx


def generate(db: Session, ctx: RequestContext, report_type: str, file_format: str, dataset_ids: list[int] | None,
             include_demo: bool) -> Report:
    if file_format not in ("pdf", "xlsx"):
        raise ValidationFailed("Formato no válido.", details=[{"field": "file_format", "message": "Usa pdf o xlsx."}])
    data = build_report_data(db, ctx, report_type, dataset_ids, include_demo)
    content = render_pdf(data) if file_format == "pdf" else render_xlsx(data)
    stored, sha = storage.save(ctx.org_id, "reports", content, file_format)
    report = Report(
        organization_id=ctx.org_id, report_type=report_type, file_format=file_format,
        title=f"{data['title']} — {data['generated_at'][:10]}", stored_filename=stored, file_sha256=sha,
        file_size=len(content), created_by_id=ctx.user_id,
        parameters={"dataset_ids": dataset_ids, "include_demo": include_demo, "period": data["period"],
                    "summary": data["summary"], "is_demo": data["is_demo"]},
    )
    db.add(report)
    db.flush()
    audit.record(db, ctx, "report.generated", entity_type="report", entity_id=report.id,
                 details={"type": report_type, "format": file_format, "sha256": sha})
    db.commit()
    return report


def list_reports(db: Session, ctx: RequestContext) -> list[Report]:
    return list(db.execute(select(Report).where(Report.organization_id == ctx.org_id).order_by(Report.id.desc()).limit(200)).scalars())
