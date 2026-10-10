from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.permissions import Role


class OrgUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    settings: dict = Field(default_factory=dict)


class MemberOut(BaseModel):
    id: int
    user_id: int
    email: str
    display_name: str
    role: str
    role_label: str
    is_active: bool
    last_login_at: datetime | None
    must_change_password: bool


class MemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=120)
    role: Role
    initial_password: str | None = Field(None, max_length=256)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        from app.services.auth import is_valid_email

        v = v.strip().lower()
        if not is_valid_email(v):
            raise ValueError("Correo electrónico no válido.")
        return v


class MemberUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class PlatformOrgCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    admin_email: str = Field(min_length=3, max_length=254)
    admin_name: str = Field(min_length=1, max_length=120)
    admin_password: str | None = Field(None, max_length=256)
    plan_code: str = "starter"


class PlatformOrgUpdate(BaseModel):
    plan_code: str | None = None
    enabled_modules: list[str] | None = None
    is_active: bool | None = None
