from __future__ import annotations

from dataclasses import dataclass, field

from app.core.errors import Forbidden
from app.core.permissions import Perm
from app.models import AuthSession, Organization, User


@dataclass
class RequestContext:
    """Who is acting, on behalf of which organization, with which permissions."""

    user: User | None
    org: Organization | None = None
    role: str | None = None
    permissions: frozenset[Perm] = field(default_factory=frozenset)
    session: AuthSession | None = None
    ip: str | None = None
    request_id: str | None = None
    is_system: bool = False

    @property
    def org_id(self) -> int:
        if self.org is None:
            raise Forbidden("Selecciona una organización para continuar.", code="organization_required")
        return self.org.id

    @property
    def actor_label(self) -> str:
        if self.is_system:
            return "system"
        return self.user.email if self.user else "anonymous"

    @property
    def user_id(self) -> int | None:
        return self.user.id if self.user else None

    def has(self, perm: Perm) -> bool:
        return perm in self.permissions

    def require(self, *perms: Perm) -> None:
        missing = [p for p in perms if p not in self.permissions]
        if missing:
            raise Forbidden(
                "No tienes permiso para realizar esta acción.",
                code="permission_denied",
                details={"missing_permissions": [str(p) for p in missing]},
            )
