from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require, require_platform_admin
from app.core.db import get_db, set_tenant
from app.core.errors import NotFound, ValidationFailed
from app.core.permissions import ROLE_LABELS, ROLE_PERMISSIONS, Perm, Role
from app.models import ALL_MODULES, AuditLog, Membership, Organization, Plan
from app.schemas.analysis import AuditOut
from app.schemas.common import Page
from app.schemas.org import MemberCreate, MemberOut, MemberUpdate, OrgUpdate, PlatformOrgCreate, PlatformOrgUpdate
from app.services import audit
from app.services import organizations as org_service
from app.services.context import RequestContext

router = APIRouter(tags=["organization"])


def _member_out(m: Membership) -> MemberOut:
    return MemberOut(
        id=m.id, user_id=m.user_id, email=m.user.email, display_name=m.user.display_name, role=m.role,
        role_label=ROLE_LABELS[Role(m.role)], is_active=m.is_active, last_login_at=m.user.last_login_at,
        must_change_password=m.user.must_change_password,
    )


@router.get("/organization", summary="Datos y configuración de la organización activa")
def get_org(ctx: RequestContext = Depends(require(Perm.ORG_SETTINGS_READ))):
    org = ctx.org
    return {"id": org.id, "name": org.name, "slug": org.slug, "plan": org.plan.code if org.plan else None,
            "modules": org.modules, "limits": org.limits, "settings": {**org_service.DEFAULT_ORG_SETTINGS, **(org.settings or {})}}


@router.patch("/organization", summary="Actualizar nombre y parámetros de la organización")
def update_org(body: OrgUpdate, ctx: RequestContext = Depends(require(Perm.ORG_SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    _validate_settings(body.settings)
    org = org_service.update_settings(db, ctx, body.name, body.settings)
    return {"id": org.id, "name": org.name, "settings": {**org_service.DEFAULT_ORG_SETTINGS, **(org.settings or {})}}


def _validate_settings(patch: dict) -> None:
    errors = []
    if "currency" in patch and not (isinstance(patch["currency"], str) and len(patch["currency"]) == 3):
        errors.append({"field": "currency", "message": "Código ISO de 3 letras (ej. MXN)."})
    if "decimal_separator" in patch and patch["decimal_separator"] not in (".", ","):
        errors.append({"field": "decimal_separator", "message": "Usa '.' o ','."})
    if "date_format" in patch and patch["date_format"] not in ("dayfirst", "monthfirst"):
        errors.append({"field": "date_format", "message": "Usa dayfirst o monthfirst."})
    for key, lo, hi in (("inventory_service_level_z", 0, 4), ("anomaly_robust_z_threshold", 2, 10),
                        ("inventory_obsolete_days", 30, 3650), ("preventive_tolerance_days", 0, 60)):
        if key in patch and not (isinstance(patch[key], (int, float)) and lo <= patch[key] <= hi):
            errors.append({"field": key, "message": f"Debe estar entre {lo} y {hi}."})
    if "inventory_abc_thresholds" in patch:
        t = patch["inventory_abc_thresholds"]
        if not (isinstance(t, list) and len(t) == 2 and all(isinstance(x, (int, float)) for x in t) and 0 < t[0] < t[1] < 1):
            errors.append({"field": "inventory_abc_thresholds", "message": "Dos proporciones crecientes entre 0 y 1, ej. [0.8, 0.95]."})
    if errors:
        raise ValidationFailed("Configuración no válida.", details=errors)


@router.get("/organization/roles", summary="Roles disponibles y sus permisos")
def roles(ctx: RequestContext = Depends(require(Perm.USERS_READ))):
    return [{"role": r.value, "label": ROLE_LABELS[r], "permissions": sorted(str(p) for p in ROLE_PERMISSIONS[r])} for r in Role]


@router.get("/organization/members", response_model=list[MemberOut], summary="Usuarios de la organización")
def members(ctx: RequestContext = Depends(require(Perm.USERS_READ)), db: Session = Depends(get_db)):
    return [_member_out(m) for m in org_service.list_members(db, ctx)]


@router.post("/organization/members", response_model=MemberOut, status_code=201, summary="Agregar usuario")
def add_member(body: MemberCreate, ctx: RequestContext = Depends(require(Perm.USERS_MANAGE)), db: Session = Depends(get_db)):
    membership, _ = org_service.add_member(db, ctx, email=body.email, display_name=body.display_name, role=body.role,
                                           initial_password=body.initial_password)
    return _member_out(membership)


@router.patch("/organization/members/{membership_id}", response_model=MemberOut, summary="Cambiar rol o desactivar usuario")
def update_member(membership_id: int, body: MemberUpdate, ctx: RequestContext = Depends(require(Perm.USERS_MANAGE)),
                  db: Session = Depends(get_db)):
    return _member_out(org_service.update_member(db, ctx, membership_id, role=body.role, is_active=body.is_active))


@router.get("/audit", response_model=Page[AuditOut], summary="Registro de auditoría de la organización")
def audit_log(
    action: str | None = None,
    actor: str | None = None,
    entity_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ctx: RequestContext = Depends(require(Perm.AUDIT_READ)),
    db: Session = Depends(get_db),
):
    stmt = select(AuditLog).where(AuditLog.organization_id == ctx.org_id)
    if action:
        stmt = stmt.where(AuditLog.action.startswith(action))
    if actor:
        stmt = stmt.where(AuditLog.actor_label.ilike(f"%{actor[:100]}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).scalars()
    return Page(items=[AuditOut.model_validate(r) for r in rows], total=total or 0, page=page, page_size=page_size)


# --- Platform administration (no access to tenant data) -------------------------------------------

platform = APIRouter(prefix="/platform", tags=["platform"])


def _org_row(db: Session, o: Organization) -> dict:
    users = db.scalar(select(func.count()).select_from(Membership).where(Membership.organization_id == o.id,
                                                                         Membership.is_active.is_(True)))
    return {"id": o.id, "name": o.name, "slug": o.slug, "plan": o.plan.code if o.plan else None, "modules": o.modules,
            "is_active": o.is_active, "active_users": users, "created_at": o.created_at}


@platform.get("/organizations", summary="Listar organizaciones (administrador de plataforma)")
def list_orgs(ctx: RequestContext = Depends(require_platform_admin), db: Session = Depends(get_db)):
    return [_org_row(db, o) for o in db.execute(select(Organization).order_by(Organization.id)).scalars()]


@platform.get("/plans", summary="Planes comerciales")
def list_plans(ctx: RequestContext = Depends(require_platform_admin), db: Session = Depends(get_db)):
    org_service.ensure_default_plans(db)
    db.commit()
    return [{"code": p.code, "name": p.name, "description": p.description, "limits": p.limits, "modules": p.modules}
            for p in db.execute(select(Plan).order_by(Plan.id)).scalars()]


@platform.post("/organizations", status_code=201, summary="Crear organización con su administrador")
def create_org(body: PlatformOrgCreate, ctx: RequestContext = Depends(require_platform_admin), db: Session = Depends(get_db)):
    org, _ = org_service.create_organization(db, name=body.name, admin_email=body.admin_email, admin_name=body.admin_name,
                                             admin_password=body.admin_password, plan_code=body.plan_code, actor=ctx)
    db.commit()
    return _org_row(db, org)


@platform.patch("/organizations/{org_id}", summary="Cambiar plan, módulos o estado de una organización")
def update_org_platform(org_id: int, body: PlatformOrgUpdate, ctx: RequestContext = Depends(require_platform_admin),
                        db: Session = Depends(get_db)):
    org = db.get(Organization, org_id)
    if org is None:
        raise NotFound("Organización no encontrada.")
    changes = {}
    if body.plan_code is not None:
        plan = db.execute(select(Plan).where(Plan.code == body.plan_code)).scalar_one_or_none()
        if plan is None:
            raise ValidationFailed("Plan desconocido.", details=[{"field": "plan_code", "message": "No existe."}])
        changes["plan"] = {"from": org.plan.code if org.plan else None, "to": plan.code}
        org.plan = plan
    if body.enabled_modules is not None:
        unknown = set(body.enabled_modules) - set(ALL_MODULES)
        if unknown:
            raise ValidationFailed("Módulos desconocidos.", details=[{"field": "enabled_modules", "message": ", ".join(sorted(unknown))}])
        changes["modules"] = {"from": org.modules, "to": body.enabled_modules}
        org.enabled_modules = body.enabled_modules
    if body.is_active is not None:
        changes["is_active"] = {"from": org.is_active, "to": body.is_active}
        org.is_active = body.is_active
    # The audit row belongs to the target organization (required by row-level security).
    set_tenant(db, org.id)
    audit.record(db, ctx, "platform.organization_updated", entity_type="organization", entity_id=org.id,
                 organization_id=org.id, details=changes)
    db.commit()
    return _org_row(db, org)
