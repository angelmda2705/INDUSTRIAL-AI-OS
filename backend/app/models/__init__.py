"""Import every model so SQLAlchemy metadata (and Alembic) see all tables."""

from app.models.analysis import (  # noqa: F401
    AnalysisRun,
    Counter,
    Finding,
    FindingEvent,
    FindingNature,
    FindingStatus,
    ImpactKind,
    KpiTarget,
    KpiValue,
    Report,
)
from app.models.audit import AuditLog  # noqa: F401
from app.models.data import Dataset, DatasetRecord, ImportJob, ImportStatus  # noqa: F401
from app.models.organization import ALL_MODULES, Organization, Plan  # noqa: F401
from app.models.user import AuthSession, Membership, PasswordResetToken, User  # noqa: F401


def tenant_tables() -> list[str]:
    """Tables protected by row-level security on PostgreSQL."""
    from app.core.db import Base

    return sorted(
        mapper.class_.__tablename__
        for mapper in Base.registry.mappers
        if getattr(mapper.class_, "__tenant_table__", False)
    )
