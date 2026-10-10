"""Analysis runs, KPI targets/values, findings and reports."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, JSONType
from app.models.base import TenantMixin, TimestampMixin, UTCDateTime, utcnow
from app.models.data import Dataset


class AnalysisRun(Base, TenantMixin):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    triggered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    trigger: Mapped[str] = mapped_column(String(30), nullable=False)  # manual | import | demo
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # running | completed | failed
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    data_profile: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    dataset: Mapped[Dataset] = relationship(lazy="joined")


class KpiTarget(Base, TenantMixin, TimestampMixin):
    """Organization-defined target for a KPI. Targets are never universal defaults."""

    __tablename__ = "kpi_targets"
    __table_args__ = (UniqueConstraint("organization_id", "kpi_code", name="uq_kpi_target_org_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kpi_code: Mapped[str] = mapped_column(String(60), nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    # Tolerance (in KPI units) before a deviation is reported.
    tolerance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    owner_label: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class KpiValue(Base, TenantMixin):
    """One computed KPI value. ``status`` is ``ok`` or ``insufficient_data``."""

    __tablename__ = "kpi_values"
    __table_args__ = (Index("ix_kpi_values_lookup", "organization_id", "kpi_code", "dataset_id", "period_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    kpi_code: Mapped[str] = mapped_column(String(60), nullable=False)
    granularity: Mapped[str] = mapped_column(String(10), nullable=False)  # total | month
    dimension: Mapped[str | None] = mapped_column(String(60))  # e.g. work_center
    dimension_value: Mapped[str | None] = mapped_column(String(160))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    value: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)  # numerator/denominator...
    message: Mapped[str | None] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class FindingNature:
    STATISTICAL_ANOMALY = "statistical_anomaly"  # unusual value; cause unknown
    CONFIRMED_ISSUE = "confirmed_issue"  # condition verified by a deterministic rule on the data
    HYPOTHESIS = "hypothesis"  # plausible explanation requiring investigation


class FindingStatus:
    OPEN = "open"
    IN_REVIEW = "in_review"
    ACTION_PLANNED = "action_planned"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"

    ALL = (OPEN, IN_REVIEW, ACTION_PLANNED, RESOLVED, DISMISSED)
    TRANSITIONS = {
        OPEN: {IN_REVIEW, ACTION_PLANNED, RESOLVED, DISMISSED},
        IN_REVIEW: {OPEN, ACTION_PLANNED, RESOLVED, DISMISSED},
        ACTION_PLANNED: {IN_REVIEW, RESOLVED, DISMISSED},
        RESOLVED: {OPEN},
        DISMISSED: {OPEN},
    }


class Finding(Base, TenantMixin, TimestampMixin):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("organization_id", "fingerprint", name="uq_finding_org_fingerprint"),
        Index("ix_findings_org_status", "organization_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)  # human-readable id, e.g. HAL-000042
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    area: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    nature: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    rule_code: Mapped[str] = mapped_column(String(60), nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)  # critical | high | medium | low
    impact_amount: Mapped[float | None] = mapped_column(Float)
    impact_currency: Mapped[str | None] = mapped_column(String(3))
    impact_basis: Mapped[str | None] = mapped_column(Text)  # formula + assumptions
    confidence: Mapped[str | None] = mapped_column(String(10))  # only for statistical methods
    confidence_basis: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=FindingStatus.OPEN)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    due_date: Mapped[date | None] = mapped_column(Date)
    first_detected_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    last_detected_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    # False when the latest analysis of the dataset no longer detects the condition.
    condition_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_analysis_run_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_runs.id", ondelete="SET NULL"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    events: Mapped[list[FindingEvent]] = relationship(
        back_populates="finding", cascade="all, delete-orphan", order_by="FindingEvent.id"
    )


class FindingEvent(Base, TenantMixin):
    __tablename__ = "finding_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_label: Mapped[str] = mapped_column(String(254), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    finding: Mapped[Finding] = relationship(back_populates="events")


class Report(Base, TenantMixin):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_type: Mapped[str] = mapped_column(String(40), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf | xlsx
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(80), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class Counter(Base, TenantMixin):
    """Per-organization sequence used for human-readable codes (HAL-000001)."""

    __tablename__ = "org_counters"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_counter_org_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
