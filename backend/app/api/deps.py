"""FastAPI dependencies: authentication, tenant binding and authorization."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db, set_tenant
from app.core.errors import Forbidden, LimitExceeded, Unauthorized
from app.core.permissions import Perm, permissions_for
from app.core.rate_limit import limiter
from app.core.security import hash_token, tokens_equal
from app.models import Membership, Organization
from app.services.auth import resolve_session, touch_session
from app.services.context import RequestContext
from app.services.limits import require_module as _require_module

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Endpoints reachable while the user must still change a temporary password.
PASSWORD_CHANGE_ALLOWED = ("/api/v1/auth/me", "/api/v1/auth/change-password", "/api/v1/auth/logout")


def client_ip(request: Request) -> str | None:
    # X-Forwarded-For is only trusted when uvicorn runs with --proxy-headers
    # behind a known proxy; request.client then already reflects it.
    return request.client.host if request.client else None


def _extract_token(request: Request) -> tuple[str | None, bool]:
    """Return (token, via_cookie)."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None, False
    token = request.cookies.get(get_settings().session_cookie_name)
    return token, True


def get_context(request: Request, db: Session = Depends(get_db)) -> RequestContext:
    settings = get_settings()
    token, via_cookie = _extract_token(request)
    if not token:
        raise Unauthorized("Inicia sesión para continuar.", code="not_authenticated")
    session = resolve_session(db, token)
    if session is None:
        raise Unauthorized("Tu sesión expiró o no es válida. Inicia sesión de nuevo.", code="session_invalid")

    if via_cookie and request.method not in SAFE_METHODS:
        header = request.headers.get("x-csrf-token", "")
        if not header or not tokens_equal(hash_token(header), session.csrf_hash):
            raise Forbidden("Solicitud rechazada por protección CSRF. Recarga la página.", code="csrf_failed")

    allowed, retry = limiter.hit(f"api-user:{session.user_id}", settings.api_rate_limit_per_minute)
    if not allowed:
        raise LimitExceeded("Demasiadas solicitudes. Espera unos segundos.", details={"retry_after_seconds": int(retry) + 1})

    user = session.user
    ctx = RequestContext(
        user=user, session=session, ip=client_ip(request), request_id=getattr(request.state, "request_id", None)
    )
    if session.organization_id is not None:
        row = db.execute(
            select(Membership, Organization)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(
                Membership.user_id == user.id,
                Membership.organization_id == session.organization_id,
                Membership.is_active.is_(True),
                Organization.is_active.is_(True),
            )
        ).first()
        if row is not None:
            membership, org = row
            ctx.org, ctx.role = org, membership.role
            ctx.permissions = permissions_for(membership.role)
            set_tenant(db, org.id)
        else:
            set_tenant(db, None)
    else:
        set_tenant(db, None)

    if user.must_change_password and request.url.path not in PASSWORD_CHANGE_ALLOWED:
        raise Forbidden("Debes cambiar tu contraseña temporal antes de continuar.", code="password_change_required")

    touch_session(db, session)
    return ctx


def require(*perms: Perm, module: str | None = None) -> Callable[..., RequestContext]:
    """Dependency factory: authenticated user, active organization and permissions."""

    def dependency(ctx: RequestContext = Depends(get_context)) -> RequestContext:
        if ctx.org is None:
            raise Forbidden("Selecciona una organización activa para continuar.", code="organization_required")
        ctx.require(*perms)
        if module:
            _require_module(ctx.org, module)
        return ctx

    return dependency


def require_platform_admin(ctx: RequestContext = Depends(get_context)) -> RequestContext:
    if not ctx.user.is_platform_admin:
        raise Forbidden("Requiere administrador de plataforma.", code="platform_admin_required")
    return ctx
