"""Authentication, sessions and password recovery."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import set_tenant
from app.core.errors import Forbidden, LimitExceeded, Unauthorized, ValidationFailed
from app.core.rate_limit import limiter
from app.core.security import (
    dummy_verify,
    hash_password,
    hash_token,
    new_token,
    password_policy_errors,
    verify_password,
)
from app.models import AuthSession, Membership, Organization, PasswordResetToken, User
from app.services import audit
from app.services.context import RequestContext
from app.services.email import EmailNotConfigured, OutgoingEmail, send_email

log = logging.getLogger("app.auth")

GENERIC_LOGIN_ERROR = "Correo o contraseña incorrectos."
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_new_password(password: str, email: str | None) -> None:
    errors = password_policy_errors(password, email)
    if errors:
        raise ValidationFailed(
            "La contraseña no cumple la política de seguridad.",
            details=[{"field": "password", "message": e} for e in errors],
        )


@dataclass
class IssuedSession:
    token: str
    csrf_token: str
    session: AuthSession


def active_memberships(db: Session, user_id: int) -> list[Membership]:
    return list(
        db.execute(
            select(Membership)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(Membership.user_id == user_id, Membership.is_active.is_(True), Organization.is_active.is_(True))
            .order_by(Membership.organization_id)
        ).scalars()
    )


def issue_session(db: Session, user: User, org_id: int | None, ip: str | None, user_agent: str | None) -> IssuedSession:
    settings = get_settings()
    now = datetime.now(UTC)
    token, csrf = new_token(), new_token()
    session = AuthSession(
        token_hash=hash_token(token),
        csrf_hash=hash_token(csrf),
        user_id=user.id,
        organization_id=org_id,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.session_absolute_timeout_hours),
        ip_address=ip,
        user_agent=(user_agent or "")[:300] or None,
    )
    db.add(session)
    return IssuedSession(token=token, csrf_token=csrf, session=session)


def login(
    db: Session,
    email: str,
    password: str,
    *,
    organization_id: int | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> IssuedSession:
    settings = get_settings()
    email = normalize_email(email)
    for key in (f"login-ip:{ip}", f"login-email:{email}"):
        allowed, retry = limiter.hit(key, settings.login_rate_limit_per_minute)
        if not allowed:
            raise LimitExceeded(
                "Demasiados intentos de inicio de sesión. Espera un momento e inténtalo de nuevo.",
                details={"retry_after_seconds": int(retry) + 1},
            )

    anon = RequestContext(user=None, ip=ip, request_id=request_id)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not user.is_active:
        dummy_verify()
        audit.record(db, anon, "auth.login_failed", details={"reason": "unknown_or_inactive"}, actor_label=email[:254])
        db.commit()
        raise Unauthorized(GENERIC_LOGIN_ERROR, code="invalid_credentials")

    now = datetime.now(UTC)
    password_ok = verify_password(password, user.password_hash)
    if user.locked_until and user.locked_until > now:
        if password_ok:
            minutes = int((user.locked_until - now).total_seconds() // 60) + 1
            raise Unauthorized(
                f"Cuenta bloqueada temporalmente por intentos fallidos. Inténtalo en {minutes} minuto(s).",
                code="account_locked",
            )
        raise Unauthorized(GENERIC_LOGIN_ERROR, code="invalid_credentials")

    if not password_ok:
        user.failed_login_count += 1
        details = {"reason": "bad_password", "failed_count": user.failed_login_count}
        if user.failed_login_count >= settings.max_failed_logins:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_count = 0
            details["locked_until"] = user.locked_until.isoformat()
        audit.record(
            db, RequestContext(user=user, ip=ip, request_id=request_id), "auth.login_failed",
            entity_type="user", entity_id=user.id, details=details,
        )
        db.commit()
        raise Unauthorized(GENERIC_LOGIN_ERROR, code="invalid_credentials")

    memberships = active_memberships(db, user.id)
    chosen: Membership | None = None
    if organization_id is not None:
        chosen = next((m for m in memberships if m.organization_id == organization_id), None)
        if chosen is None:
            raise Forbidden("No tienes acceso a esa organización.", code="organization_forbidden")
    elif memberships:
        chosen = memberships[0]
    if chosen is None and not user.is_platform_admin:
        raise Forbidden("Tu usuario no tiene acceso a ninguna organización activa.", code="no_organization")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    org_id = chosen.organization_id if chosen else None
    set_tenant(db, org_id)
    issued = issue_session(db, user, org_id, ip, user_agent)
    audit.record(
        db, RequestContext(user=user, ip=ip, request_id=request_id), "auth.login",
        entity_type="user", entity_id=user.id, organization_id=org_id,
    )
    db.commit()
    return issued


def resolve_session(db: Session, token: str) -> AuthSession | None:
    """Return a valid (not revoked, not expired, not idle) session for the token."""
    settings = get_settings()
    session = db.execute(select(AuthSession).where(AuthSession.token_hash == hash_token(token))).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        return None
    now = datetime.now(UTC)
    if session.expires_at <= now:
        return None
    if now - session.last_seen_at > timedelta(minutes=settings.session_idle_timeout_minutes):
        return None
    if not session.user.is_active:
        return None
    return session


def touch_session(db: Session, session: AuthSession) -> None:
    now = datetime.now(UTC)
    if now - session.last_seen_at > timedelta(seconds=60):
        session.last_seen_at = now
        db.commit()


def logout(db: Session, ctx: RequestContext) -> None:
    if ctx.session is not None:
        ctx.session.revoked_at = datetime.now(UTC)
        audit.record(db, ctx, "auth.logout", entity_type="user", entity_id=ctx.user_id)
        db.commit()


def revoke_all_sessions(db: Session, user_id: int, except_session_id: int | None = None) -> None:
    stmt = update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    if except_session_id is not None:
        stmt = stmt.where(AuthSession.id != except_session_id)
    db.execute(stmt.values(revoked_at=datetime.now(UTC)))


def switch_organization(db: Session, ctx: RequestContext, organization_id: int) -> Membership:
    membership = next((m for m in active_memberships(db, ctx.user.id) if m.organization_id == organization_id), None)
    if membership is None:
        raise Forbidden("No tienes acceso a esa organización.", code="organization_forbidden")
    ctx.session.organization_id = organization_id
    set_tenant(db, organization_id)
    audit.record(db, ctx, "auth.switch_organization", organization_id=organization_id,
                 entity_type="organization", entity_id=organization_id)
    db.commit()
    return membership


def change_password(db: Session, ctx: RequestContext, current_password: str, new_password: str) -> None:
    user = ctx.user
    if not verify_password(current_password, user.password_hash):
        raise ValidationFailed(
            "La contraseña actual no es correcta.",
            details=[{"field": "current_password", "message": "La contraseña actual no es correcta."}],
        )
    if current_password == new_password:
        raise ValidationFailed(
            "La nueva contraseña debe ser diferente.",
            details=[{"field": "new_password", "message": "Debe ser diferente a la actual."}],
        )
    validate_new_password(new_password, user.email)
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = datetime.now(UTC)
    revoke_all_sessions(db, user.id, except_session_id=ctx.session.id if ctx.session else None)
    audit.record(db, ctx, "auth.password_changed", entity_type="user", entity_id=user.id)
    db.commit()


def request_password_reset(db: Session, email: str, ip: str | None, request_id: str | None) -> None:
    """Create a one-time reset token and e-mail it. Always behaves the same for unknown e-mails."""
    settings = get_settings()
    email = normalize_email(email)
    allowed, _ = limiter.hit(f"pwreset:{ip}", 5, 600)
    allowed_email, _ = limiter.hit(f"pwreset-email:{email}", 3, 900)
    if not (allowed and allowed_email):
        raise LimitExceeded("Demasiadas solicitudes de recuperación. Inténtalo más tarde.")
    user = db.execute(select(User).where(User.email == email, User.is_active.is_(True))).scalar_one_or_none()
    if user is None:
        return
    now = datetime.now(UTC)
    token = new_token()
    db.add(
        PasswordResetToken(
            token_hash=hash_token(token),
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(minutes=settings.password_reset_ttl_minutes),
        )
    )
    audit.record(db, RequestContext(user=user, ip=ip, request_id=request_id), "auth.password_reset_requested",
                 entity_type="user", entity_id=user.id)
    db.commit()
    link = f"{settings.public_app_url.rstrip('/')}/reset-password#token={token}"
    try:
        send_email(
            OutgoingEmail(
                to=user.email,
                subject=f"{settings.brand_name}: recuperación de acceso",
                body=(
                    "Recibimos una solicitud para restablecer tu contraseña.\n\n"
                    f"Usa este enlace dentro de los próximos {settings.password_reset_ttl_minutes} minutos:\n{link}\n\n"
                    "Si no solicitaste el cambio, ignora este mensaje."
                ),
            )
        )
    except EmailNotConfigured:
        log.error("password_reset_email_not_configured")
    except Exception:  # noqa: BLE001 - SMTP errors must not leak to the client
        log.exception("password_reset_email_failed")


def confirm_password_reset(db: Session, token: str, new_password: str, ip: str | None, request_id: str | None) -> None:
    now = datetime.now(UTC)
    row = db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise ValidationFailed("El enlace de recuperación no es válido o ya expiró. Solicita uno nuevo.",
                               code="invalid_reset_token")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise ValidationFailed("El enlace de recuperación no es válido o ya expiró.", code="invalid_reset_token")
    validate_new_password(new_password, user.email)
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = now
    user.failed_login_count = 0
    user.locked_until = None
    row.used_at = now
    # Invalidate every other outstanding token and every session.
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    revoke_all_sessions(db, user.id)
    audit.record(db, RequestContext(user=user, ip=ip, request_id=request_id), "auth.password_reset_completed",
                 entity_type="user", entity_id=user.id)
    db.commit()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email)) and len(email) <= 254
