from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_context
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Conflict, Forbidden
from app.core.permissions import ROLE_LABELS, Role, permissions_for
from app.models import AuthSession, User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginOut,
    LoginRequest,
    MembershipBrief,
    MeOut,
    OrgBrief,
    ResetConfirm,
    ResetRequest,
    SignupRequest,
    SwitchOrgRequest,
    UserOut,
)
from app.schemas.common import Message
from app.services import auth as auth_service
from app.services.auth import active_memberships
from app.services.context import RequestContext
from app.services.organizations import create_organization

router = APIRouter(prefix="/auth", tags=["auth"])


def _role_label(role: str | None) -> str | None:
    return ROLE_LABELS.get(Role(role)) if role else None


def build_me(db: Session, user: User, session: AuthSession | None) -> MeOut:
    memberships = active_memberships(db, user.id)
    current = next((m for m in memberships if session and m.organization_id == session.organization_id), None)
    org = current.organization if current else None
    return MeOut(
        user=UserOut.model_validate(user),
        organization=OrgBrief(
            id=org.id, name=org.name, slug=org.slug, plan_code=org.plan.code if org.plan else None,
            plan_name=org.plan.name if org.plan else None, modules=org.modules, limits=org.limits,
            settings=org.settings or {},
        ) if org else None,
        role=current.role if current else None,
        role_label=_role_label(current.role) if current else None,
        permissions=sorted(str(p) for p in permissions_for(current.role)) if current else [],
        memberships=[
            MembershipBrief(organization_id=m.organization_id, organization_name=m.organization.name, role=m.role,
                            role_label=_role_label(m.role))
            for m in memberships
        ],
        session_expires_at=session.expires_at if session else None,
    )


def _set_cookies(response: Response, token: str, csrf: str) -> None:
    s = get_settings()
    max_age = s.session_absolute_timeout_hours * 3600
    response.set_cookie(s.session_cookie_name, token, max_age=max_age, httponly=True, secure=s.cookie_secure,
                        samesite=s.cookie_samesite, path="/")
    # Readable by the frontend so it can echo it in the X-CSRF-Token header (double submit).
    response.set_cookie(s.csrf_cookie_name, csrf, max_age=max_age, httponly=False, secure=s.cookie_secure,
                        samesite=s.cookie_samesite, path="/")


def _clear_cookies(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(s.session_cookie_name, path="/")
    response.delete_cookie(s.csrf_cookie_name, path="/")


@router.post("/login", response_model=LoginOut, summary="Iniciar sesión")
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    issued = auth_service.login(
        db, body.email, body.password, organization_id=body.organization_id, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), request_id=getattr(request.state, "request_id", None),
    )
    _set_cookies(response, issued.token, issued.csrf_token)
    me = build_me(db, issued.session.user, issued.session)
    return LoginOut(me=me, csrf_token=issued.csrf_token, access_token=issued.token if body.issue_bearer_token else None)


@router.post("/logout", response_model=Message, summary="Cerrar sesión")
def logout(response: Response, ctx: RequestContext = Depends(get_context), db: Session = Depends(get_db)):
    auth_service.logout(db, ctx)
    _clear_cookies(response)
    return Message(message="Sesión cerrada.")


@router.get("/me", response_model=MeOut, summary="Usuario y organización actuales")
def me(ctx: RequestContext = Depends(get_context), db: Session = Depends(get_db)):
    return build_me(db, ctx.user, ctx.session)


@router.post("/switch-organization", response_model=MeOut, summary="Cambiar de organización activa")
def switch_org(body: SwitchOrgRequest, ctx: RequestContext = Depends(get_context), db: Session = Depends(get_db)):
    auth_service.switch_organization(db, ctx, body.organization_id)
    return build_me(db, ctx.user, ctx.session)


@router.post("/change-password", response_model=Message, summary="Cambiar contraseña")
def change_password(body: ChangePasswordRequest, ctx: RequestContext = Depends(get_context), db: Session = Depends(get_db)):
    auth_service.change_password(db, ctx, body.current_password, body.new_password)
    return Message(message="Contraseña actualizada. Se cerraron tus otras sesiones.")


@router.post("/password-reset/request", response_model=Message, status_code=202, summary="Solicitar recuperación de acceso")
def reset_request(body: ResetRequest, request: Request, db: Session = Depends(get_db)):
    auth_service.request_password_reset(db, body.email, client_ip(request), getattr(request.state, "request_id", None))
    return Message(message="Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.")


@router.post("/password-reset/confirm", response_model=Message, summary="Restablecer contraseña con enlace")
def reset_confirm(body: ResetConfirm, request: Request, db: Session = Depends(get_db)):
    auth_service.confirm_password_reset(db, body.token, body.new_password, client_ip(request),
                                        getattr(request.state, "request_id", None))
    return Message(message="Contraseña restablecida. Ya puedes iniciar sesión.")


@router.post("/signup", response_model=LoginOut, status_code=201, summary="Registrar una organización (si está habilitado)")
def signup(body: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    if not get_settings().allow_self_signup:
        raise Forbidden("El registro de organizaciones está deshabilitado. Contacta al administrador de la plataforma.",
                        code="signup_disabled")
    if db.execute(select(User.id).where(User.email == body.email)).first():
        raise Conflict("Ya existe una cuenta con ese correo. Inicia sesión o recupera tu acceso.")
    org, user = create_organization(db, name=body.organization_name, admin_email=body.email,
                                    admin_name=body.display_name, admin_password=body.password)
    db.commit()
    issued = auth_service.issue_session(db, user, org.id, client_ip(request), request.headers.get("user-agent"))
    db.commit()
    _set_cookies(response, issued.token, issued.csrf_token)
    return LoginOut(me=build_me(db, user, issued.session), csrf_token=issued.csrf_token)
