"""Plan limits and module enablement checks (enforced server-side)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, PlanLimitExceeded
from app.models import ImportJob, Membership, Organization


def require_module(org: Organization, module: str) -> None:
    if module not in org.modules:
        raise Forbidden(
            f"El módulo '{module}' no está habilitado para tu organización.",
            code="module_disabled",
            details={"module": module},
        )


def _limit(org: Organization, key: str) -> int | None:
    value = org.limits.get(key)
    return int(value) if value is not None else None


def check_user_limit(db: Session, org: Organization) -> None:
    limit = _limit(org, "max_users")
    if limit is None:
        return
    count = db.scalar(
        select(func.count()).select_from(Membership).where(
            Membership.organization_id == org.id, Membership.is_active.is_(True)
        )
    )
    if count >= limit:
        raise PlanLimitExceeded(
            f"Tu plan permite hasta {limit} usuarios activos.", details={"limit": limit, "current": count}
        )


def check_import_limit(db: Session, org: Organization) -> None:
    limit = _limit(org, "max_imports_per_month")
    if limit is None:
        return
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    count = db.scalar(
        select(func.count()).select_from(ImportJob).where(
            ImportJob.organization_id == org.id, ImportJob.created_at >= month_start, ImportJob.is_demo.is_(False)
        )
    )
    if count >= limit:
        raise PlanLimitExceeded(
            f"Tu plan permite {limit} importaciones por mes.", details={"limit": limit, "current": count}
        )


def max_rows_per_import(org: Organization, hard_limit: int) -> int:
    limit = _limit(org, "max_rows_per_import")
    return min(limit, hard_limit) if limit else hard_limit


DEFAULT_PLANS = [
    {
        "code": "starter",
        "name": "Inicial",
        "description": "Diagnóstico con importación de archivos.",
        "limits": {"max_users": 5, "max_imports_per_month": 30, "max_rows_per_import": 20_000},
        "modules": ["imports", "analytics", "findings", "kpis", "reports"],
    },
    {
        "code": "professional",
        "name": "Profesional",
        "description": "Operación diaria de varias áreas.",
        "limits": {"max_users": 50, "max_imports_per_month": 500, "max_rows_per_import": 100_000},
        "modules": ["imports", "analytics", "findings", "kpis", "reports"],
    },
    {
        "code": "enterprise",
        "name": "Empresarial",
        "description": "Límites configurables por contrato.",
        "limits": {"max_rows_per_import": 200_000},
        "modules": ["imports", "analytics", "findings", "kpis", "reports"],
    },
]
