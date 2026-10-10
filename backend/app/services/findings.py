"""Finding workflow: listing, status changes, ownership and comments."""

from __future__ import annotations

from datetime import date

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.models import Finding, FindingEvent, FindingStatus, Membership
from app.services import audit
from app.services.context import RequestContext
from app.services.tenancy import get_owned

PRIORITY_ORDER = case(
    {"critical": 0, "high": 1, "medium": 2, "low": 3}, value=Finding.priority, else_=4
)
STATUS_LABELS = {
    "open": "Abierto", "in_review": "En revisión", "action_planned": "Acción planificada",
    "resolved": "Resuelto", "dismissed": "Descartado",
}


def list_findings(
    db: Session,
    ctx: RequestContext,
    *,
    status: list[str] | None = None,
    priority: list[str] | None = None,
    area: str | None = None,
    nature: str | None = None,
    dataset_id: int | None = None,
    active_only: bool = False,
    include_demo: bool = True,
    q: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Finding], int]:
    stmt = select(Finding).where(Finding.organization_id == ctx.org_id)
    if status:
        stmt = stmt.where(Finding.status.in_(status))
    if priority:
        stmt = stmt.where(Finding.priority.in_(priority))
    if area:
        stmt = stmt.where(Finding.area == area)
    if nature:
        stmt = stmt.where(Finding.nature == nature)
    if dataset_id:
        stmt = stmt.where(Finding.dataset_id == dataset_id)
    if active_only:
        stmt = stmt.where(Finding.condition_active.is_(True))
    if not include_demo:
        stmt = stmt.where(Finding.is_demo.is_(False))
    if q:
        like = f"%{q.strip()[:100]}%"
        stmt = stmt.where(or_(Finding.title.ilike(like), Finding.code.ilike(like), Finding.description.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.order_by(PRIORITY_ORDER, Finding.last_detected_at.desc(), Finding.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars()
    return list(rows), int(total or 0)


def _check_owner(db: Session, ctx: RequestContext, user_id: int) -> None:
    ok = db.scalar(
        select(func.count()).select_from(Membership).where(
            Membership.organization_id == ctx.org_id, Membership.user_id == user_id, Membership.is_active.is_(True)
        )
    )
    if not ok:
        raise ValidationFailed("El responsable debe ser un usuario activo de la organización.",
                               details=[{"field": "owner_user_id", "message": "Usuario no válido."}])


_UNSET = object()


def update_finding(
    db: Session,
    ctx: RequestContext,
    finding_id: int,
    *,
    status: str | None = None,
    note: str | None = None,
    owner_user_id: int | None | object = _UNSET,
    due_date: date | None | object = _UNSET,
) -> Finding:
    finding = get_owned(db, Finding, finding_id, ctx, "Hallazgo")
    note = (note or "").strip() or None
    changes: dict = {}
    if status is not None and status != finding.status:
        if status not in FindingStatus.ALL:
            raise ValidationFailed("Estado no válido.", details=[{"field": "status", "message": "Estado desconocido."}])
        if status not in FindingStatus.TRANSITIONS[finding.status]:
            raise ValidationFailed(
                f"No se puede pasar de «{STATUS_LABELS[finding.status]}» a «{STATUS_LABELS[status]}».",
                details=[{"field": "status", "message": "Transición no permitida."}],
            )
        if status in (FindingStatus.RESOLVED, FindingStatus.DISMISSED) and not note:
            raise ValidationFailed(
                "Explica la resolución o el motivo del descarte.",
                details=[{"field": "note", "message": "Obligatorio para resolver o descartar."}],
            )
        db.add(FindingEvent(
            organization_id=ctx.org_id, finding_id=finding.id, actor_user_id=ctx.user_id, actor_label=ctx.actor_label,
            event_type="status_changed", from_status=finding.status, to_status=status, note=note,
        ))
        changes["status"] = {"from": finding.status, "to": status}
        finding.status = status
        note = None  # already stored with the status change
    if owner_user_id is not _UNSET and owner_user_id != finding.owner_user_id:
        if owner_user_id is not None:
            _check_owner(db, ctx, owner_user_id)
        db.add(FindingEvent(
            organization_id=ctx.org_id, finding_id=finding.id, actor_user_id=ctx.user_id, actor_label=ctx.actor_label,
            event_type="owner_changed", data={"from": finding.owner_user_id, "to": owner_user_id},
        ))
        changes["owner_user_id"] = {"from": finding.owner_user_id, "to": owner_user_id}
        finding.owner_user_id = owner_user_id
    if due_date is not _UNSET and due_date != finding.due_date:
        db.add(FindingEvent(
            organization_id=ctx.org_id, finding_id=finding.id, actor_user_id=ctx.user_id, actor_label=ctx.actor_label,
            event_type="due_date_changed", data={"from": str(finding.due_date) if finding.due_date else None,
                                                 "to": str(due_date) if due_date else None},
        ))
        changes["due_date"] = {"from": str(finding.due_date) if finding.due_date else None, "to": str(due_date) if due_date else None}
        finding.due_date = due_date
    if note:
        db.add(FindingEvent(
            organization_id=ctx.org_id, finding_id=finding.id, actor_user_id=ctx.user_id, actor_label=ctx.actor_label,
            event_type="comment", note=note[:5000],
        ))
        changes["comment"] = True
    if not changes:
        raise ValidationFailed("No hay cambios que guardar.")
    audit.record(db, ctx, "finding.updated", entity_type="finding", entity_id=finding.id,
                 details={"code": finding.code, "changes": changes})
    db.commit()
    db.refresh(finding)
    return finding
