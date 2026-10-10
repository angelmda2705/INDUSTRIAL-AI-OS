from __future__ import annotations

import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.db import get_db
from app.core.permissions import Perm
from app.models import Dataset, Finding, Report, User
from app.schemas.analysis import (
    CommentCreate,
    FindingDetail,
    FindingEventOut,
    FindingOut,
    FindingUpdate,
    ReportCreate,
    ReportOut,
    TargetIn,
)
from app.schemas.common import Message, Page
from app.services import dashboard as dashboard_service
from app.services import findings as findings_service
from app.services import kpi_service, storage
from app.services.analytics.kpis import CATALOG
from app.services.context import RequestContext
from app.services.reports import service as report_service
from app.services.reports.builder import IMPACT_KIND_LABELS, NATURE_LABELS, PRIORITY_LABELS, REPORT_TYPES, STATUS_LABELS
from app.services.reports.render import safe_cell
from app.services.tenancy import get_owned

router = APIRouter(tags=["analysis"])


@router.get("/dashboard", summary="Panel ejecutivo")
def dashboard(area: str | None = None, dataset_id: int | None = None, include_demo: bool = True,
              ctx: RequestContext = Depends(require(Perm.DASHBOARD_READ)), db: Session = Depends(get_db)):
    return dashboard_service.build(db, ctx, area=area, dataset_id=dataset_id, include_demo=include_demo)


# --- KPIs ------------------------------------------------------------------------------


@router.get("/kpis/catalog", summary="Catálogo de indicadores con objetivos de la organización")
def catalog(ctx: RequestContext = Depends(require(Perm.KPI_READ)), db: Session = Depends(get_db)):
    targets = kpi_service.targets(db, ctx)
    return [{**k.public(), "target": kpi_service._target_dict(targets.get(k.code))} for k in CATALOG]


@router.get("/kpis/values", summary="Valores más recientes de cada indicador por conjunto de datos")
def kpi_values(include_demo: bool = True, dataset_id: int | None = None,
               ctx: RequestContext = Depends(require(Perm.KPI_READ)), db: Session = Depends(get_db)):
    return kpi_service.latest_totals(db, ctx, include_demo, dataset_id)


@router.get("/kpis/{kpi_code}", summary="Detalle de un indicador: desglose, serie mensual e historial")
def kpi_detail(kpi_code: str, dataset_id: int, ctx: RequestContext = Depends(require(Perm.KPI_READ)),
               db: Session = Depends(get_db)):
    return kpi_service.kpi_detail(db, ctx, kpi_code, dataset_id)


@router.put("/kpis/{kpi_code}/target", summary="Definir objetivo del indicador")
def set_target(kpi_code: str, body: TargetIn, ctx: RequestContext = Depends(require(Perm.KPI_MANAGE)),
               db: Session = Depends(get_db)):
    t = kpi_service.set_target(db, ctx, kpi_code, body.target_value, body.tolerance, body.owner_label, body.notes)
    return kpi_service._target_dict(t)


@router.delete("/kpis/{kpi_code}/target", response_model=Message, summary="Eliminar objetivo del indicador")
def delete_target(kpi_code: str, ctx: RequestContext = Depends(require(Perm.KPI_MANAGE)), db: Session = Depends(get_db)):
    kpi_service.delete_target(db, ctx, kpi_code)
    return Message(message="Objetivo eliminado.")


# --- Findings ---------------------------------------------------------------------------


@router.get("/findings", response_model=Page[FindingOut], summary="Hallazgos")
def list_findings(
    status: list[str] | None = Query(None),
    priority: list[str] | None = Query(None),
    area: str | None = None,
    nature: str | None = None,
    dataset_id: int | None = None,
    active_only: bool = False,
    include_demo: bool = True,
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    ctx: RequestContext = Depends(require(Perm.FINDINGS_READ)),
    db: Session = Depends(get_db),
):
    rows, total = findings_service.list_findings(
        db, ctx, status=status, priority=priority, area=area, nature=nature, dataset_id=dataset_id, active_only=active_only,
        include_demo=include_demo, q=q, page=page, page_size=page_size,
    )
    return Page(items=[FindingOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/findings/export", summary="Exportar hallazgos a Excel")
def export_findings(include_demo: bool = True, ctx: RequestContext = Depends(require(Perm.FINDINGS_READ)),
                    db: Session = Depends(get_db)):
    rows, _ = findings_service.list_findings(db, ctx, include_demo=include_demo, page=1, page_size=100_000)
    wb = Workbook()
    ws = wb.active
    ws.title = "Hallazgos"
    ws.append(["Código", "Título", "Área", "Naturaleza", "Prioridad", "Estado", "Condición vigente", "Detectado",
               "Último análisis", "Método", "Recomendación", "Impacto (monto)", "Tipo de impacto", "Moneda", "Base del impacto",
               "Confianza", "Demo"])
    for f in rows:
        ws.append([safe_cell(v) for v in (
            f.code, f.title, f.area, NATURE_LABELS.get(f.nature, f.nature), PRIORITY_LABELS.get(f.priority, f.priority),
            STATUS_LABELS.get(f.status, f.status), "Sí" if f.condition_active else "No",
            f.first_detected_at.strftime("%Y-%m-%d %H:%M"), f.last_detected_at.strftime("%Y-%m-%d %H:%M"), f.method,
            f.recommendation, f.impact_amount, IMPACT_KIND_LABELS.get(f.impact_kind) if f.impact_kind else None,
            f.impact_currency, f.impact_basis, f.confidence, "Sí" if f.is_demo else "No")])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": 'attachment; filename="hallazgos.xlsx"'})


def _detail(db: Session, f: Finding) -> FindingDetail:
    detail = FindingDetail.model_validate(f)
    detail.events = [FindingEventOut.model_validate(e) for e in f.events]
    if f.dataset_id:
        ds = db.get(Dataset, f.dataset_id)
        detail.dataset_name = ds.name if ds else None
    if f.owner_user_id:
        owner = db.get(User, f.owner_user_id)
        detail.owner_name = owner.display_name if owner else None
    return detail


@router.get("/findings/{finding_id}", response_model=FindingDetail, summary="Detalle del hallazgo con evidencia e historial")
def get_finding(finding_id: int, ctx: RequestContext = Depends(require(Perm.FINDINGS_READ)), db: Session = Depends(get_db)):
    return _detail(db, get_owned(db, Finding, finding_id, ctx, "Hallazgo"))


@router.patch("/findings/{finding_id}", response_model=FindingDetail, summary="Cambiar estado, responsable o fecha límite")
def update_finding(finding_id: int, body: FindingUpdate, ctx: RequestContext = Depends(require(Perm.FINDINGS_UPDATE)),
                   db: Session = Depends(get_db)):
    kwargs = {}
    fields = body.model_fields_set
    if "owner_user_id" in fields:
        kwargs["owner_user_id"] = body.owner_user_id
    if "due_date" in fields:
        kwargs["due_date"] = body.due_date
    f = findings_service.update_finding(db, ctx, finding_id, status=body.status, note=body.note, **kwargs)
    return _detail(db, f)


@router.post("/findings/{finding_id}/comments", response_model=FindingDetail, status_code=201, summary="Agregar comentario")
def comment(finding_id: int, body: CommentCreate, ctx: RequestContext = Depends(require(Perm.FINDINGS_UPDATE)),
            db: Session = Depends(get_db)):
    return _detail(db, findings_service.update_finding(db, ctx, finding_id, note=body.note))


# --- Reports ---------------------------------------------------------------------------------


@router.get("/reports/types", summary="Tipos de reporte disponibles")
def report_types(ctx: RequestContext = Depends(require(Perm.REPORTS_GENERATE))):
    return [{"code": code, "title": title, "area": area} for code, (title, area) in REPORT_TYPES.items()]


@router.get("/reports", response_model=list[ReportOut], summary="Reportes generados")
def list_reports(ctx: RequestContext = Depends(require(Perm.REPORTS_GENERATE)), db: Session = Depends(get_db)):
    return report_service.list_reports(db, ctx)


@router.post("/reports", response_model=ReportOut, status_code=201, summary="Generar reporte PDF o Excel")
def create_report(body: ReportCreate, ctx: RequestContext = Depends(require(Perm.REPORTS_GENERATE, module="reports")),
                  db: Session = Depends(get_db)):
    return report_service.generate(db, ctx, body.report_type, body.file_format, body.dataset_ids, body.include_demo)


@router.get("/reports/{report_id}/download", summary="Descargar reporte")
def download_report(report_id: int, ctx: RequestContext = Depends(require(Perm.REPORTS_GENERATE)),
                    db: Session = Depends(get_db)):
    report = get_owned(db, Report, report_id, ctx, "Reporte")
    path = storage.path_for(ctx.org_id, "reports", report.stored_filename)
    media = "application/pdf" if report.file_format == "pdf" else \
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(path, media_type=media, filename=f"reporte_{report.report_type}_{report.id}.{report.file_format}")

