"""Organizations, plans and memberships."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import set_tenant
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.permissions import Role, can_assign_role
from app.core.security import hash_password
from app.models import Membership, Organization, Plan, User
from app.services import audit
from app.services.auth import normalize_email, validate_new_password
from app.services.context import RequestContext
from app.services.limits import DEFAULT_PLANS, check_user_limit

DEFAULT_ORG_SETTINGS = {
    "currency": "MXN",
    "timezone": "America/Mexico_City",
    "date_format": "dayfirst",
    "decimal_separator": ".",
    # Analysis parameters (documented in docs/KPI_CATALOG.md)
    "inventory_service_level_z": 1.645,
    "inventory_abc_thresholds": [0.8, 0.95],
    "inventory_obsolete_days": 180,
    "anomaly_robust_z_threshold": 3.5,
    "preventive_tolerance_days": 0,
}


def ensure_default_plans(db: Session) -> None:
    existing = {p.code for p in db.execute(select(Plan)).scalars()}
    for spec in DEFAULT_PLANS:
        if spec["code"] not in existing:
            db.add(Plan(**spec))
    db.flush()


def slugify(name: str) -> str:
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:60] or "organizacion"


def _unique_slug(db: Session, name: str) -> str:
    base = slugify(name)
    slug, n = base, 1
    while db.scalar(select(func.count()).select_from(Organization).where(Organization.slug == slug)):
        n += 1
        slug = f"{base}-{n}"
    return slug


def create_organization(
    db: Session,
    *,
    name: str,
    admin_email: str,
    admin_name: str,
    admin_password: str | None,
    plan_code: str = "starter",
    actor: RequestContext | None = None,
) -> tuple[Organization, User]:
    """Create an organization with its first administrator (does not commit)."""
    name = name.strip()
    if len(name) < 2:
        raise ValidationFailed("El nombre de la organización es obligatorio.",
                               details=[{"field": "organization_name", "message": "Mínimo 2 caracteres."}])
    ensure_default_plans(db)
    plan = db.execute(select(Plan).where(Plan.code == plan_code)).scalar_one_or_none()
    if plan is None:
        raise ValidationFailed("El plan indicado no existe.", details=[{"field": "plan_code", "message": "Plan desconocido."}])
    org = Organization(name=name, slug=_unique_slug(db, name), plan=plan, settings=dict(DEFAULT_ORG_SETTINGS))
    db.add(org)
    db.flush()
    set_tenant(db, org.id)

    email = normalize_email(admin_email)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        if not admin_password:
            raise ValidationFailed("Se requiere una contraseña para el nuevo usuario.")
        validate_new_password(admin_password, email)
        user = User(email=email, display_name=admin_name.strip() or email, password_hash=hash_password(admin_password))
        db.add(user)
        db.flush()
    db.add(Membership(user_id=user.id, organization_id=org.id, role=Role.ORG_ADMIN))
    audit.record(
        db, actor, "organization.created", entity_type="organization", entity_id=org.id,
        organization_id=org.id, details={"name": org.name, "plan": plan.code, "admin_user_id": user.id},
        actor_label=None if actor else "system",
    )
    return org, user


def update_settings(db: Session, ctx: RequestContext, name: str | None, settings_patch: dict) -> Organization:
    org = ctx.org
    changes: dict = {}
    if name is not None and name.strip() and name.strip() != org.name:
        changes["name"] = {"from": org.name, "to": name.strip()}
        org.name = name.strip()
    if settings_patch:
        merged = dict(org.settings or {})
        for key, value in settings_patch.items():
            if key not in DEFAULT_ORG_SETTINGS:
                raise ValidationFailed(f"Configuración desconocida: {key}", details=[{"field": key, "message": "No permitido."}])
            if merged.get(key) != value:
                changes[key] = {"from": merged.get(key), "to": value}
                merged[key] = value
        org.settings = merged
    if changes:
        audit.record(db, ctx, "organization.settings_updated", entity_type="organization", entity_id=org.id,
                     details={"changes": changes})
    db.commit()
    return org


def org_setting(org: Organization, key: str):
    return (org.settings or {}).get(key, DEFAULT_ORG_SETTINGS.get(key))


# --- Members -----------------------------------------------------------------


def list_members(db: Session, ctx: RequestContext) -> list[Membership]:
    return list(
        db.execute(
            select(Membership).where(Membership.organization_id == ctx.org_id).order_by(Membership.id)
        ).scalars()
    )


def _get_membership(db: Session, ctx: RequestContext, membership_id: int) -> Membership:
    m = db.execute(
        select(Membership).where(Membership.id == membership_id, Membership.organization_id == ctx.org_id)
    ).scalar_one_or_none()
    if m is None:
        raise NotFound("Usuario no encontrado en esta organización.")
    return m


def _active_admin_count(db: Session, org_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Membership).where(
            Membership.organization_id == org_id, Membership.role == Role.ORG_ADMIN, Membership.is_active.is_(True)
        )
    )


def add_member(
    db: Session, ctx: RequestContext, *, email: str, display_name: str, role: str, initial_password: str | None
) -> tuple[Membership, bool]:
    """Add a user to the organization. Returns (membership, created_new_user)."""
    if not can_assign_role(ctx.role, role):
        raise Forbidden("No puedes asignar ese rol.", code="role_assignment_forbidden")
    check_user_limit(db, ctx.org)
    email = normalize_email(email)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    created = False
    if user is None:
        if not initial_password:
            raise ValidationFailed(
                "Indica una contraseña temporal para el nuevo usuario.",
                details=[{"field": "initial_password", "message": "Obligatoria para usuarios nuevos."}],
            )
        validate_new_password(initial_password, email)
        user = User(
            email=email,
            display_name=display_name.strip() or email,
            password_hash=hash_password(initial_password),
            must_change_password=True,
        )
        db.add(user)
        db.flush()
        created = True
    existing = db.execute(
        select(Membership).where(Membership.user_id == user.id, Membership.organization_id == ctx.org_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise Conflict("Ese usuario ya pertenece a la organización.")
    membership = Membership(user_id=user.id, organization_id=ctx.org_id, role=role)
    db.add(membership)
    db.flush()
    audit.record(db, ctx, "membership.created", entity_type="membership", entity_id=membership.id,
                 details={"user_id": user.id, "email": email, "role": role, "new_user": created})
    db.commit()
    return membership, created


def update_member(db: Session, ctx: RequestContext, membership_id: int, *, role: str | None, is_active: bool | None) -> Membership:
    m = _get_membership(db, ctx, membership_id)
    changes: dict = {}
    if m.user_id == ctx.user_id and (role not in (None, m.role) or is_active is False):
        raise Forbidden("No puedes cambiar tu propio rol ni desactivarte.", code="self_modification_forbidden")
    if m.role == Role.ORG_ADMIN and ctx.role != Role.ORG_ADMIN:
        raise Forbidden("Solo un administrador puede modificar a otro administrador.")
    if role is not None and role != m.role:
        if not can_assign_role(ctx.role, role):
            raise Forbidden("No puedes asignar ese rol.", code="role_assignment_forbidden")
        changes["role"] = {"from": m.role, "to": role}
        m.role = role
    if is_active is not None and is_active != m.is_active:
        if is_active:
            check_user_limit(db, ctx.org)
        changes["is_active"] = {"from": m.is_active, "to": is_active}
        m.is_active = is_active
    db.flush()
    if _active_admin_count(db, ctx.org_id) == 0:
        db.rollback()
        raise Conflict("La organización debe conservar al menos un administrador activo.")
    if changes:
        audit.record(db, ctx, "membership.updated", entity_type="membership", entity_id=m.id,
                     details={"user_id": m.user_id, "changes": changes})
    db.commit()
    return m
