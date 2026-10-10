"""Role-based access control.

Permissions are checked on the backend for every sensitive operation through
``require_permission`` (see ``app/api/deps.py``). The frontend only uses the
permission list returned by ``/auth/me`` to hide actions the user cannot run;
it is never the enforcement point.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ORG_ADMIN = "org_admin"
    DIRECTOR = "director"
    MANAGER = "manager"
    SUPERVISOR = "supervisor"
    ANALYST = "analyst"
    OPERATOR = "operator"
    AUDITOR = "auditor"


ROLE_LABELS: dict[Role, str] = {
    Role.ORG_ADMIN: "Administrador de empresa",
    Role.DIRECTOR: "Director",
    Role.MANAGER: "Gerente",
    Role.SUPERVISOR: "Supervisor",
    Role.ANALYST: "Analista",
    Role.OPERATOR: "Operador",
    Role.AUDITOR: "Auditor (solo lectura)",
}


class Perm(StrEnum):
    DASHBOARD_READ = "dashboard.read"
    ORG_SETTINGS_READ = "org.settings.read"
    ORG_SETTINGS_MANAGE = "org.settings.manage"
    USERS_READ = "users.read"
    USERS_MANAGE = "users.manage"
    AUDIT_READ = "audit.read"
    DATA_READ = "data.read"
    DATA_IMPORT = "data.import"
    DATA_DELETE = "data.delete"
    ANALYSIS_RUN = "analysis.run"
    KPI_READ = "kpi.read"
    KPI_MANAGE = "kpi.manage"
    FINDINGS_READ = "findings.read"
    FINDINGS_UPDATE = "findings.update"
    REPORTS_GENERATE = "reports.generate"
    DEMO_MANAGE = "demo.manage"


_READ_ONLY = {
    Perm.DASHBOARD_READ,
    Perm.DATA_READ,
    Perm.KPI_READ,
    Perm.FINDINGS_READ,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Perm]] = {
    Role.ORG_ADMIN: frozenset(Perm),
    Role.DIRECTOR: frozenset(
        _READ_ONLY
        | {
            Perm.ORG_SETTINGS_READ,
            Perm.USERS_READ,
            Perm.AUDIT_READ,
            Perm.ANALYSIS_RUN,
            Perm.KPI_MANAGE,
            Perm.FINDINGS_UPDATE,
            Perm.REPORTS_GENERATE,
        }
    ),
    Role.MANAGER: frozenset(
        _READ_ONLY
        | {
            Perm.ORG_SETTINGS_READ,
            Perm.USERS_READ,
            Perm.DATA_IMPORT,
            Perm.DATA_DELETE,
            Perm.ANALYSIS_RUN,
            Perm.KPI_MANAGE,
            Perm.FINDINGS_UPDATE,
            Perm.REPORTS_GENERATE,
            Perm.DEMO_MANAGE,
        }
    ),
    Role.SUPERVISOR: frozenset(
        _READ_ONLY | {Perm.DATA_IMPORT, Perm.ANALYSIS_RUN, Perm.FINDINGS_UPDATE, Perm.REPORTS_GENERATE}
    ),
    Role.ANALYST: frozenset(
        _READ_ONLY
        | {
            Perm.DATA_IMPORT,
            Perm.DATA_DELETE,
            Perm.ANALYSIS_RUN,
            Perm.FINDINGS_UPDATE,
            Perm.REPORTS_GENERATE,
            Perm.DEMO_MANAGE,
        }
    ),
    Role.OPERATOR: frozenset({Perm.DASHBOARD_READ, Perm.DATA_IMPORT, Perm.KPI_READ, Perm.FINDINGS_READ}),
    Role.AUDITOR: frozenset(
        _READ_ONLY | {Perm.ORG_SETTINGS_READ, Perm.USERS_READ, Perm.AUDIT_READ, Perm.REPORTS_GENERATE}
    ),
}


def permissions_for(role: str) -> frozenset[Perm]:
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return frozenset()


def can_assign_role(actor_role: str, target_role: str) -> bool:
    """Only organization administrators may grant the administrator role."""
    if Role(target_role) == Role.ORG_ADMIN:
        return Role(actor_role) == Role.ORG_ADMIN
    return Perm.USERS_MANAGE in permissions_for(actor_role)
