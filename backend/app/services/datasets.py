from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, Dataset, DatasetRecord, Finding, FindingEvent, ImportJob, KpiValue
from app.services import audit
from app.services.context import RequestContext
from app.services.tenancy import get_owned


def list_datasets(db: Session, ctx: RequestContext) -> list[Dataset]:
    return list(
        db.execute(select(Dataset).where(Dataset.organization_id == ctx.org_id).order_by(Dataset.created_at.desc())).scalars()
    )


def records_page(db: Session, ctx: RequestContext, dataset: Dataset, page: int, page_size: int) -> tuple[list[DatasetRecord], int]:
    base = select(DatasetRecord).where(DatasetRecord.dataset_id == dataset.id, DatasetRecord.organization_id == ctx.org_id)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.execute(base.order_by(DatasetRecord.id).offset((page - 1) * page_size).limit(page_size)).scalars()
    return list(rows), int(total or 0)


def latest_run(db: Session, ctx: RequestContext, dataset_id: int, completed_only: bool = True) -> AnalysisRun | None:
    stmt = select(AnalysisRun).where(AnalysisRun.organization_id == ctx.org_id, AnalysisRun.dataset_id == dataset_id)
    if completed_only:
        stmt = stmt.where(AnalysisRun.status == "completed")
    return db.execute(stmt.order_by(AnalysisRun.id.desc()).limit(1)).scalar_one_or_none()


def purge_dataset(db: Session, org_id: int, dataset_id: int) -> None:
    """Delete a dataset and everything derived from it (explicit, not relying on FK cascades)."""
    db.execute(delete(KpiValue).where(KpiValue.dataset_id == dataset_id, KpiValue.organization_id == org_id))
    findings = select(Finding.id).where(Finding.dataset_id == dataset_id, Finding.organization_id == org_id)
    db.execute(delete(FindingEvent).where(FindingEvent.finding_id.in_(findings), FindingEvent.organization_id == org_id))
    db.execute(delete(Finding).where(Finding.dataset_id == dataset_id, Finding.organization_id == org_id))
    db.execute(delete(AnalysisRun).where(AnalysisRun.dataset_id == dataset_id, AnalysisRun.organization_id == org_id))
    db.execute(delete(DatasetRecord).where(DatasetRecord.dataset_id == dataset_id, DatasetRecord.organization_id == org_id))
    for job in db.execute(select(ImportJob).where(ImportJob.target_dataset_id == dataset_id, ImportJob.organization_id == org_id)).scalars():
        job.target_dataset_id = None
    db.execute(delete(Dataset).where(Dataset.id == dataset_id, Dataset.organization_id == org_id))


def delete_dataset(db: Session, ctx: RequestContext, dataset_id: int) -> None:
    ds = get_owned(db, Dataset, dataset_id, ctx, "Conjunto de datos")
    info = {"name": ds.name, "rows": ds.row_count, "template": ds.template_code, "is_demo": ds.is_demo}
    purge_dataset(db, ctx.org_id, ds.id)
    audit.record(db, ctx, "dataset.deleted", entity_type="dataset", entity_id=dataset_id, details=info)
    db.commit()
