from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, JSONType
from app.models.base import UTCDateTime, utcnow


class AuditLog(Base):
    """Append-only record of relevant actions (no update/delete endpoints exist).

    ``organization_id`` is nullable only for platform-level events such as a
    failed login for an unknown account. Tenant users only ever see rows of
    their own organization.
    """

    __tablename__ = "audit_logs"
    __tenant_table__ = True
    # implicit_returning=False: on PostgreSQL, INSERT ... RETURNING would also apply the
    # RLS read policy, which rejects platform-level rows (organization_id NULL). Without
    # RETURNING only the WITH CHECK clause applies, so those rows can be written but
    # remain invisible to every tenant session.
    __table_args__ = (Index("ix_audit_org_created", "organization_id", "created_at"), {"implicit_returning": False})

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_label: Mapped[str] = mapped_column(String(254), nullable=False)  # e-mail or "system"
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(60))
    details: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
