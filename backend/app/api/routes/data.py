from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import ValidationFailed
from app.core.permissions import Perm
from app.models import AnalysisRun, Dataset, ImportJob
from app.schemas.common import Message, Page
from app.schemas.data import (
    AnalysisRunOut,
    CommitRequest,
    DatasetOut,
    ImportJobOut,
    RecordOut,
    ValidateRequest,
)
from app.services import datasets as dataset_service
from app.services import demo as demo_service
from app.services.analytics.engine import prepared_frame, run_analysis
from app.services.analytics.kpis import kpis_for_template
from app.services.context import RequestContext
from app.services.imports import service as import_service
from app.services.imports.templates import TEMPLATES, get_template
from app.services.organizations import DEFAULT_ORG_SETTINGS
from app.services.reports.render import safe_cell
from app.services.tenancy import get_owned

router = APIRouter(tags=["data"])
MODULE = "imports"


@router.get("/imports/templates", summary="Plantillas de importación disponibles")
def templates(ctx: RequestContext = Depends(require(Perm.DATA_READ))):
    return [
        {
            "code": t.code, "name": t.name, "area": t.area, "description": t.description, "generic": t.generic,
            "key_fields": list(t.key_fields),
            "fields": [{"name": f.name, "label": f.label, "type": f.type, "required": f.required, "description": f.description,
                        "choices": list(f.choices)} for f in t.fields],
            "kpis": [k.code for k in kpis_for_template(t.code)],
        }
        for t in TEMPLATES.values()
    ]


@router.get("/imports", response_model=Page[ImportJobOut], summary="Historial de importaciones")
def list_imports(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                 ctx: RequestContext = Depends(require(Perm.DATA_READ)), db: Session = Depends(get_db)):
    stmt = select(ImportJob).where(ImportJob.organization_id == ctx.org_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(ImportJob.id.desc()).offset((page - 1) * page_size).limit(page_size)).scalars()
    return Page(items=[ImportJobOut.model_validate(r) for r in rows], total=total or 0, page=page, page_size=page_size)


@router.post("/imports", response_model=ImportJobOut, status_code=201, summary="Cargar archivo CSV o Excel")
async def upload(file: UploadFile = File(...), ctx: RequestContext = Depends(require(Perm.DATA_IMPORT, module=MODULE)),
                 db: Session = Depends(get_db)):
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise ValidationFailed(f"El archivo excede el máximo de {get_settings().max_upload_mb} MB.", code="file_too_large")
    return import_service.upload(db, ctx, file.filename or "archivo", data)


@router.get("/imports/{job_id}", response_model=ImportJobOut, summary="Detalle de una importación")
def get_import(job_id: int, ctx: RequestContext = Depends(require(Perm.DATA_READ)), db: Session = Depends(get_db)):
    return get_owned(db, ImportJob, job_id, ctx, "Importación")


@router.get("/imports/{job_id}/preview", summary="Columnas detectadas, vista previa y mapeo sugerido")
def preview(job_id: int, sheet: str | None = None, ctx: RequestContext = Depends(require(Perm.DATA_READ)),
            db: Session = Depends(get_db)):
    job = get_owned(db, ImportJob, job_id, ctx, "Importación")
    return import_service.preview(db, ctx, job, sheet)


@router.post("/imports/{job_id}/validate", summary="Mapear columnas y validar todos los renglones")
def validate(job_id: int, body: ValidateRequest, ctx: RequestContext = Depends(require(Perm.DATA_IMPORT, module=MODULE)),
             db: Session = Depends(get_db)):
    job = get_owned(db, ImportJob, job_id, ctx, "Importación")
    summary = import_service.validate(
        db, ctx, job, template_code=body.template_code, mapping=body.mapping, dataset_id=body.dataset_id,
        dataset_name=body.dataset_name, sheet_name=body.sheet_name, decimal_separator=body.decimal_separator,
        date_format=body.date_format,
    )
    return {"job": ImportJobOut.model_validate(job), "summary": summary}


@router.post("/imports/{job_id}/commit", summary="Confirmar la importación (y analizar)")
def commit(job_id: int, body: CommitRequest, ctx: RequestContext = Depends(require(Perm.DATA_IMPORT, module=MODULE)),
           db: Session = Depends(get_db)):
    job = import_service.commit(db, ctx, job_id, skip_invalid=body.skip_invalid, skip_duplicates=body.skip_duplicates,
                                dataset_description=body.dataset_description)
    run = None
    if body.run_analysis and "analytics" in ctx.org.modules:
        dataset = get_owned(db, Dataset, job.target_dataset_id, ctx, "Conjunto de datos")
        run = run_analysis(db, ctx, dataset, trigger="import")
    return {"job": ImportJobOut.model_validate(job), "analysis_run": AnalysisRunOut.model_validate(run) if run else None}


@router.post("/imports/{job_id}/revert", summary="Revertir una importación confirmada")
def revert(job_id: int, ctx: RequestContext = Depends(require(Perm.DATA_DELETE, module=MODULE)), db: Session = Depends(get_db)):
    job = import_service.revert(db, ctx, job_id)
    run = None
    if job.target_dataset_id and "analytics" in ctx.org.modules:
        dataset = get_owned(db, Dataset, job.target_dataset_id, ctx, "Conjunto de datos")
        run = run_analysis(db, ctx, dataset, trigger="import")
    return {"job": ImportJobOut.model_validate(job), "analysis_run": AnalysisRunOut.model_validate(run) if run else None}


@router.delete("/imports/{job_id}", response_model=Message, summary="Descartar una importación no confirmada")
def discard(job_id: int, ctx: RequestContext = Depends(require(Perm.DATA_IMPORT)), db: Session = Depends(get_db)):
    job = get_owned(db, ImportJob, job_id, ctx, "Importación")
    import_service.discard(db, ctx, job)
    return Message(message="Importación descartada.")


# --- Datasets ---------------------------------------------------------------------


@router.get("/datasets", response_model=list[DatasetOut], summary="Conjuntos de datos")
def list_datasets(ctx: RequestContext = Depends(require(Perm.DATA_READ)), db: Session = Depends(get_db)):
    return dataset_service.list_datasets(db, ctx)


@router.get("/datasets/{dataset_id}", summary="Conjunto de datos con su último perfil de calidad")
def get_dataset(dataset_id: int, ctx: RequestContext = Depends(require(Perm.DATA_READ)), db: Session = Depends(get_db)):
    ds = get_owned(db, Dataset, dataset_id, ctx, "Conjunto de datos")
    run = dataset_service.latest_run(db, ctx, ds.id)
    imports_ = db.execute(select(ImportJob).where(ImportJob.organization_id == ctx.org_id, ImportJob.target_dataset_id == ds.id)
                          .order_by(ImportJob.id)).scalars()
    template = get_template(ds.template_code)
    return {
        "dataset": DatasetOut.model_validate(ds),
        "template": {"code": template.code, "name": template.name, "area": template.area,
                     "fields": [{"name": f.name, "label": f.label, "type": f.type} for f in template.fields]},
        "latest_run": AnalysisRunOut.model_validate(run) if run else None,
        "profile": run.data_profile if run else None,
        "imports": [ImportJobOut.model_validate(j) for j in imports_],
    }


@router.get("/datasets/{dataset_id}/records", response_model=Page[RecordOut], summary="Registros (paginados)")
def records(dataset_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
            ctx: RequestContext = Depends(require(Perm.DATA_READ)), db: Session = Depends(get_db)):
    ds = get_owned(db, Dataset, dataset_id, ctx, "Conjunto de datos")
    rows, total = dataset_service.records_page(db, ctx, ds, page, page_size)
    return Page(items=[RecordOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/datasets/{dataset_id}/runs", response_model=list[AnalysisRunOut], summary="Historial de análisis")
def runs(dataset_id: int, ctx: RequestContext = Depends(require(Perm.DATA_READ)), db: Session = Depends(get_db)):
    ds = get_owned(db, Dataset, dataset_id, ctx, "Conjunto de datos")
    return list(db.execute(select(AnalysisRun).where(AnalysisRun.organization_id == ctx.org_id, AnalysisRun.dataset_id == ds.id)
                           .order_by(AnalysisRun.id.desc()).limit(50)).scalars())


@router.post("/datasets/{dataset_id}/analyze", response_model=AnalysisRunOut, summary="Ejecutar análisis")
def analyze(dataset_id: int, ctx: RequestContext = Depends(require(Perm.ANALYSIS_RUN, module="analytics")),
            db: Session = Depends(get_db)):
    ds = get_owned(db, Dataset, dataset_id, ctx, "Conjunto de datos")
    return run_analysis(db, ctx, ds, trigger="manual")


@router.delete("/datasets/{dataset_id}", response_model=Message, summary="Eliminar conjunto de datos y sus resultados")
def delete_dataset(dataset_id: int, ctx: RequestContext = Depends(require(Perm.DATA_DELETE)), db: Session = Depends(get_db)):
    dataset_service.delete_dataset(db, ctx, dataset_id)
    return Message(message="Conjunto de datos eliminado.")


INVENTORY_COLUMNS = [
    ("sku", "SKU"), ("description", "Descripción"), ("category", "Categoría"), ("warehouse", "Almacén"),
    ("on_hand_qty", "Existencia"), ("unit_cost", "Costo unitario"), ("_value", "Valor"), ("_abc", "Clase ABC"),
    ("avg_daily_demand", "Demanda diaria"), ("lead_time_days", "Lead time (días)"), ("_safety_stock", "Stock de seguridad"),
    ("_rop", "Punto de reorden"), ("_rop_basis", "Base ROP"), ("_coverage_days", "Cobertura (días)"),
    ("max_qty", "Máximo"), ("_suggested_order_qty", "Cantidad sugerida"), ("_days_without_movement", "Días sin movimiento"),
]


@router.get("/datasets/{dataset_id}/inventory-analysis", summary="Análisis por artículo (ABC, ROP, cobertura)")
def inventory_analysis(dataset_id: int, ctx: RequestContext = Depends(require(Perm.DATA_READ)), db: Session = Depends(get_db)):
    ds = get_owned(db, Dataset, dataset_id, ctx, "Conjunto de datos")
    if ds.template_code != "inventory_items":
        raise ValidationFailed("Este análisis solo aplica a conjuntos de existencias de inventario.")
    df = prepared_frame(db, ds, {**DEFAULT_ORG_SETTINGS, **(ctx.org.settings or {})})
    if df.empty:
        return {"columns": [{"key": k, "label": label} for k, label in INVENTORY_COLUMNS], "items": [], "reference_date": None}
    items = []
    for _, row in df.iterrows():
        item = {}
        for col, _ in INVENTORY_COLUMNS:
            v = row.get(col)
            if v is None or isinstance(v, str):
                item[col] = v
            elif pd.isna(v):
                item[col] = None
            else:
                item[col] = round(float(v), 3)
        if row["_negative"]:
            item["status"] = "negativo"
        elif row["_stockout"]:
            item["status"] = "sin existencia"
        elif row["_below_rop"]:
            item["status"] = "bajo ROP"
        elif pd.notna(row["_excess_qty"]):
            item["status"] = "exceso"
        else:
            item["status"] = "normal"
        items.append(item)
    return {"columns": [{"key": k, "label": label} for k, label in INVENTORY_COLUMNS], "items": items,
            "reference_date": df.attrs.get("obsolescence_reference_date")}


@router.get("/datasets/{dataset_id}/export", summary="Exportar registros a Excel")
def export_dataset(dataset_id: int, ctx: RequestContext = Depends(require(Perm.DATA_READ)), db: Session = Depends(get_db)):
    ds = get_owned(db, Dataset, dataset_id, ctx, "Conjunto de datos")
    template = get_template(ds.template_code)
    rows, _ = dataset_service.records_page(db, ctx, ds, 1, 1_000_000)
    if template.generic:
        cols = sorted({k for r in rows for k in r.data})
        labels = cols
    else:
        cols = [f.name for f in template.fields]
        labels = [f.label for f in template.fields]
    wb = Workbook()
    ws = wb.active
    ws.title = "Registros"
    ws.append(["Renglón origen", "Importación #"] + labels)
    for r in rows:
        ws.append([r.source_row, r.import_job_id] + [safe_cell(r.data.get(c)) for c in cols])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"dataset_{ds.id}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# --- Demo data -----------------------------------------------------------------------


@router.post("/demo", summary="Cargar datos de demostración (identificados como DEMO)")
def load_demo(ctx: RequestContext = Depends(require(Perm.DEMO_MANAGE)), db: Session = Depends(get_db)):
    datasets = demo_service.load_demo(db, ctx)
    return {"datasets": [DatasetOut.model_validate(d) for d in datasets]}


@router.delete("/demo", response_model=Message, summary="Eliminar todos los datos de demostración")
def remove_demo(ctx: RequestContext = Depends(require(Perm.DEMO_MANAGE)), db: Session = Depends(get_db)):
    n = demo_service.remove_demo(db, ctx)
    return Message(message=f"Se eliminaron {n} conjuntos de datos de demostración.")
