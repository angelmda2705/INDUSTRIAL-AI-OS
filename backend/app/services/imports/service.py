"""Import workflow: upload → preview → map & validate → commit → (revert).

Every step is persisted on ``ImportJob`` so the process is auditable and can
be resumed. The commit re-reads and re-validates the stored file instead of
trusting the earlier preview, and inserts all rows in one transaction.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models import Dataset, DatasetRecord, ImportJob, ImportStatus
from app.services import audit, storage
from app.services.context import RequestContext
from app.services.imports.parsing import (
    ParsedTable,
    column_profiles,
    detect_file_type,
    jsonable,
    read_table,
)
from app.services.imports.templates import TEMPLATES, get_template
from app.services.imports.validation import ParseOptions, check_mapping, suggest_mapping, validate_rows
from app.services.limits import check_import_limit, max_rows_per_import
from app.services.organizations import org_setting
from app.services.tenancy import get_owned

PREVIEW_ROWS = 20


def _max_rows(ctx: RequestContext) -> int:
    return max_rows_per_import(ctx.org, get_settings().max_rows_per_import_hard_limit)


def _read(job: ImportJob, ctx: RequestContext, sheet: str | None = None) -> ParsedTable:
    settings = get_settings()
    path = storage.path_for(ctx.org_id, "imports", job.stored_filename)
    return read_table(
        path,
        job.file_type,
        max_rows=_max_rows(ctx),
        max_uncompressed=settings.max_xlsx_uncompressed_mb * 1024 * 1024,
        sheet=sheet if sheet is not None else job.sheet_name,
    )


def upload(db: Session, ctx: RequestContext, filename: str, data: bytes, *, is_demo: bool = False) -> ImportJob:
    settings = get_settings()
    if not data:
        raise ValidationFailed("El archivo está vacío.", code="empty_file")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise ValidationFailed(f"El archivo excede el máximo de {settings.max_upload_mb} MB.", code="file_too_large")
    if not is_demo:
        check_import_limit(db, ctx.org)
    safe_name = (filename or "archivo").replace("\\", "/").split("/")[-1][:255]
    file_type = detect_file_type(safe_name, data)
    stored, sha = storage.save(ctx.org_id, "imports", data, file_type)
    job = ImportJob(
        organization_id=ctx.org_id,
        created_by_id=ctx.user_id,
        original_filename=safe_name,
        stored_filename=stored,
        file_type=file_type,
        file_size=len(data),
        file_sha256=sha,
        status=ImportStatus.PARSED,
        is_demo=is_demo,
    )
    try:
        table = _read(job, ctx)
    except ValidationFailed:
        storage.delete(ctx.org_id, "imports", stored)
        raise
    job.sheet_names = table.sheet_names
    job.sheet_name = table.sheet_name
    job.detected_columns = table.columns
    job.total_rows = table.total_rows
    job.parse_options = {
        "decimal_separator": org_setting(ctx.org, "decimal_separator"),
        "date_format": org_setting(ctx.org, "date_format"),
        "csv_delimiter": table.delimiter,
        "encoding": table.encoding,
    }
    db.add(job)
    db.flush()
    audit.record(db, ctx, "import.uploaded", entity_type="import_job", entity_id=job.id,
                 details={"filename": safe_name, "sha256": sha, "size": len(data), "rows": table.total_rows})
    db.commit()
    return job


def previously_committed_with_same_file(db: Session, ctx: RequestContext, job: ImportJob) -> list[int]:
    return list(
        db.execute(
            select(ImportJob.id).where(
                ImportJob.organization_id == ctx.org_id,
                ImportJob.file_sha256 == job.file_sha256,
                ImportJob.status == ImportStatus.COMMITTED,
                ImportJob.id != job.id,
            )
        ).scalars()
    )


def preview(db: Session, ctx: RequestContext, job: ImportJob, sheet: str | None = None) -> dict:
    if sheet is not None and sheet != job.sheet_name:
        if job.status in (ImportStatus.COMMITTED, ImportStatus.REVERTED):
            raise Conflict("No se puede cambiar la hoja de una importación confirmada.")
        table = _read(job, ctx, sheet)
        job.sheet_name, job.detected_columns, job.total_rows = sheet, table.columns, table.total_rows
        job.status, job.validation_summary = ImportStatus.PARSED, {}
        db.commit()
    else:
        table = _read(job, ctx)
    suggestions = {code: suggest_mapping(t, table.columns) for code, t in TEMPLATES.items() if not t.generic}
    return {
        "columns": column_profiles(table),
        "rows": [
            {"row": n, "values": [jsonable(v) for v in values]} for n, values in table.rows[:PREVIEW_ROWS]
        ],
        "total_rows": table.total_rows,
        "sheet_names": job.sheet_names,
        "sheet_name": job.sheet_name,
        "suggested_mappings": suggestions,
        "same_file_committed_import_ids": previously_committed_with_same_file(db, ctx, job),
    }


def _resolve_target(db: Session, ctx: RequestContext, template_code: str, dataset_id: int | None, new_name: str | None) -> tuple[Dataset | None, str | None]:
    if dataset_id is not None:
        ds = get_owned(db, Dataset, dataset_id, ctx, "Conjunto de datos")
        if ds.template_code != template_code:
            raise ValidationFailed("El conjunto de datos destino usa otra plantilla.",
                                   details=[{"field": "dataset_id", "message": "La plantilla no coincide."}])
        return ds, None
    name = (new_name or "").strip()
    if len(name) < 3:
        raise ValidationFailed("Indica un nombre para el nuevo conjunto de datos.",
                               details=[{"field": "dataset_name", "message": "Mínimo 3 caracteres."}])
    exists = db.scalar(
        select(func.count()).select_from(Dataset).where(Dataset.organization_id == ctx.org_id, Dataset.name == name)
    )
    if exists:
        raise ValidationFailed("Ya existe un conjunto de datos con ese nombre.",
                               details=[{"field": "dataset_name", "message": "Elige otro nombre o agrega al existente."}])
    return None, name[:160]


def _existing_fingerprints(db: Session, dataset_id: int | None) -> set[str]:
    if dataset_id is None:
        return set()
    return set(db.execute(select(DatasetRecord.fingerprint).where(DatasetRecord.dataset_id == dataset_id)).scalars())


def _options(job: ImportJob, decimal_separator: str | None, date_format: str | None) -> ParseOptions:
    opts = ParseOptions(
        decimal_separator=decimal_separator or job.parse_options.get("decimal_separator", "."),
        date_format=date_format or job.parse_options.get("date_format", "dayfirst"),
    )
    if opts.decimal_separator not in (".", ","):
        raise ValidationFailed("Separador decimal no válido.", details=[{"field": "decimal_separator", "message": "Usa '.' o ','."}])
    if opts.date_format not in ("dayfirst", "monthfirst"):
        raise ValidationFailed("Formato de fecha no válido.", details=[{"field": "date_format", "message": "Usa dayfirst o monthfirst."}])
    return opts


def validate(
    db: Session,
    ctx: RequestContext,
    job: ImportJob,
    *,
    template_code: str,
    mapping: dict[str, str],
    dataset_id: int | None,
    dataset_name: str | None,
    sheet_name: str | None = None,
    decimal_separator: str | None = None,
    date_format: str | None = None,
) -> dict:
    if job.status in (ImportStatus.COMMITTED, ImportStatus.REVERTED):
        raise Conflict("Esta importación ya fue confirmada o revertida.")
    template = get_template(template_code)
    if template is None:
        raise ValidationFailed("Plantilla desconocida.", details=[{"field": "template_code", "message": "No existe."}])
    if sheet_name is not None and sheet_name != job.sheet_name:
        preview(db, ctx, job, sheet_name)
    table = _read(job, ctx)
    mapping = {k: v for k, v in (mapping or {}).items() if v}
    if template.generic:
        mapping = {c: c for c in table.columns}
    problems = check_mapping(template, mapping, table.columns)
    if problems:
        raise ValidationFailed("El mapeo de columnas está incompleto o es incorrecto.", details=problems)
    target, new_name = _resolve_target(db, ctx, template_code, dataset_id, dataset_name)
    opts = _options(job, decimal_separator, date_format)
    result = validate_rows(template, mapping, table, opts, _existing_fingerprints(db, target.id if target else None))
    unmapped = [c for c in table.columns if c not in set(mapping.values())]
    summary = result.summary(table.total_rows, unmapped)

    job.template_code = template_code
    job.column_mapping = mapping
    job.parse_options = {**job.parse_options, "decimal_separator": opts.decimal_separator, "date_format": opts.date_format}
    job.target_dataset_id = target.id if target else None
    job.target_dataset_name = target.name if target else new_name
    job.validation_summary = summary
    job.valid_rows = summary["valid_rows"]
    job.invalid_rows = summary["invalid_rows"]
    job.duplicate_rows = summary["duplicate_rows"]
    job.status = ImportStatus.VALIDATED
    audit.record(db, ctx, "import.validated", entity_type="import_job", entity_id=job.id,
                 details={k: summary[k] for k in ("total_rows", "valid_rows", "invalid_rows", "duplicate_rows")}
                 | {"template": template_code})
    db.commit()
    return summary


def commit(
    db: Session,
    ctx: RequestContext,
    job_id: int,
    *,
    skip_invalid: bool,
    skip_duplicates: bool,
    dataset_description: str | None = None,
) -> ImportJob:
    job = _claim(db, ctx, job_id, ImportStatus.VALIDATED, ImportStatus.COMMITTING,
                 "La importación debe validarse antes de confirmarse (o ya fue confirmada).")
    template = get_template(job.template_code)
    table = _read(job, ctx)
    target: Dataset | None = None
    if job.target_dataset_id is not None:
        target = get_owned(db, Dataset, job.target_dataset_id, ctx, "Conjunto de datos")
        # Serialize concurrent appends to the same dataset before reading its fingerprints.
        db.execute(update(Dataset).where(Dataset.id == target.id).values(row_count=Dataset.row_count)
                   .execution_options(synchronize_session=False))
    opts = _options(job, None, None)
    result = validate_rows(template, job.column_mapping, table, opts, _existing_fingerprints(db, target.id if target else None))
    if result.error_rows and not skip_invalid:
        raise ValidationFailed(
            f"Hay {result.error_rows} renglones con errores. Corrígelos o confirma omitiéndolos.",
            code="rows_with_errors",
        )
    dup_rows = {d["row"] for d in result.duplicate_in_file} | set(result.duplicate_existing)
    rows = [r for r in result.valid if not (skip_duplicates and r.source_row in dup_rows)]
    if not rows:
        raise ValidationFailed("No hay renglones válidos para importar.", code="nothing_to_import")

    if target is None:
        _, name = _resolve_target(db, ctx, job.template_code, None, job.target_dataset_name)
        target = Dataset(
            organization_id=ctx.org_id,
            name=name,
            description=dataset_description,
            template_code=job.template_code,
            is_demo=job.is_demo,
            created_by_id=ctx.user_id,
        )
        db.add(target)
        db.flush()
    db.execute(
        insert(DatasetRecord),
        [
            {
                "organization_id": ctx.org_id,
                "dataset_id": target.id,
                "import_job_id": job.id,
                "source_row": r.source_row,
                "fingerprint": r.fingerprint,
                "data": r.data,
            }
            for r in rows
        ],
    )
    target.row_count = (target.row_count or 0) + len(rows)
    target.analysis_stale = True
    now = datetime.now(UTC)
    job.target_dataset_id = target.id
    job.imported_rows = len(rows)
    job.status = ImportStatus.COMMITTED
    job.committed_at = now
    job.validation_summary = {
        **job.validation_summary,
        "commit": {
            "imported_rows": len(rows),
            "skipped_invalid_rows": result.error_rows,
            "skipped_duplicate_rows": len(result.valid) - len(rows),
            "skip_invalid": skip_invalid,
            "skip_duplicates": skip_duplicates,
        },
    }
    audit.record(db, ctx, "import.committed", entity_type="import_job", entity_id=job.id,
                 details={"dataset_id": target.id, "imported_rows": len(rows), "file_sha256": job.file_sha256})
    db.commit()
    return job


def _claim(db: Session, ctx: RequestContext, job_id: int, from_status: str, to_status: str, conflict_msg: str) -> ImportJob:
    """Atomically move a job between states (compare-and-set).

    The conditional UPDATE takes a row lock (PostgreSQL) or the write lock
    (SQLite), so of two concurrent requests only one can claim the job; the
    other sees ``rowcount == 0`` once the first transaction finishes. If the
    caller fails afterwards, the session rollback restores the previous status.
    """
    claimed = db.execute(
        update(ImportJob)
        .where(ImportJob.id == job_id, ImportJob.organization_id == ctx.org_id, ImportJob.status == from_status)
        .values(status=to_status)
        .execution_options(synchronize_session=False)
    ).rowcount
    job = db.execute(
        select(ImportJob).where(ImportJob.id == job_id, ImportJob.organization_id == ctx.org_id)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if job is None:
        raise NotFound("Importación no encontrada.")
    if not claimed:
        raise Conflict(conflict_msg)
    return job


def revert(db: Session, ctx: RequestContext, job_id: int) -> ImportJob:
    job = _claim(db, ctx, job_id, ImportStatus.COMMITTED, ImportStatus.REVERTED,
                 "Solo se pueden revertir importaciones confirmadas.")
    deleted = db.execute(
        delete(DatasetRecord).where(
            DatasetRecord.import_job_id == job.id, DatasetRecord.organization_id == ctx.org_id
        )
    ).rowcount
    if job.target_dataset_id:
        ds = get_owned(db, Dataset, job.target_dataset_id, ctx, "Conjunto de datos")
        ds.row_count = max(0, (ds.row_count or 0) - deleted)
        ds.analysis_stale = True
    job.status = ImportStatus.REVERTED
    job.reverted_at = datetime.now(UTC)
    audit.record(db, ctx, "import.reverted", entity_type="import_job", entity_id=job.id,
                 details={"deleted_rows": deleted, "dataset_id": job.target_dataset_id})
    db.commit()
    return job


def discard(db: Session, ctx: RequestContext, job: ImportJob) -> None:
    if job.status in (ImportStatus.COMMITTED, ImportStatus.REVERTED):
        raise Conflict("Una importación confirmada o revertida se conserva para trazabilidad; no se puede descartar.")
    storage.delete(ctx.org_id, "imports", job.stored_filename)
    audit.record(db, ctx, "import.discarded", entity_type="import_job", entity_id=job.id,
                 details={"filename": job.original_filename})
    db.delete(job)
    db.commit()
