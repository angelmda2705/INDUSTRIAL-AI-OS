from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORM


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    organization_id: int | None = None
    issue_bearer_token: bool = Field(False, description="Devuelve el token en el cuerpo (solo para integraciones/scripts).")


class SwitchOrgRequest(BaseModel):
    organization_id: int


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class ResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=1, max_length=256)


class SignupRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        from app.services.auth import is_valid_email

        v = v.strip().lower()
        if not is_valid_email(v):
            raise ValueError("Correo electrónico no válido.")
        return v


class UserOut(ORM):
    id: int
    email: str
    display_name: str
    is_platform_admin: bool
    must_change_password: bool
    last_login_at: datetime | None = None


class OrgBrief(BaseModel):
    id: int
    name: str
    slug: str
    plan_code: str | None
    plan_name: str | None
    modules: list[str]
    limits: dict
    settings: dict


class MembershipBrief(BaseModel):
    organization_id: int
    organization_name: str
    role: str
    role_label: str


class MeOut(BaseModel):
    user: UserOut
    organization: OrgBrief | None
    role: str | None
    role_label: str | None
    permissions: list[str]
    memberships: list[MembershipBrief]
    session_expires_at: datetime | None


class LoginOut(BaseModel):
    me: MeOut
    csrf_token: str
    access_token: str | None = None
