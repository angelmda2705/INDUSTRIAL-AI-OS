"""Imported data: import jobs, datasets and their records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, JSONType
from app.models.base import TenantMixin, TimestampMixin, UTCDateTime


class ImportStatus:
    PARSED = "parsed"
    VALIDATED = "validated"
    COMMITTING = "committing"  # transient, only visible inside the committing transaction
    COMMITTED = "committed"
    REVERTED = "reverted"
    FAILED = "failed"


class Dataset(Base, TenantMixin, TimestampMixin):
    """A named collection of records that follow one import template."""

    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_dataset_org_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    template_code: Mapped[str] = mapped_column(String(60), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    last_analyzed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # True when records changed after the latest analysis.
    analysis_stale: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ImportJob(Base, TenantMixin, TimestampMixin):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(80), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # csv | xlsx
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ImportStatus.PARSED)
    sheet_names: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(120))
    detected_columns: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    template_code: Mapped[str | None] = mapped_column(String(60))
    column_mapping: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    parse_options: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    target_dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    target_dataset_name: Mapped[str | None] = mapped_column(String(160))
    validation_summary: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    committed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reverted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_message: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    target_dataset: Mapped[Dataset | None] = relationship(lazy="joined")


class DatasetRecord(Base, TenantMixin):
    """One validated row. ``data`` holds normalized values keyed by template field."""

    __tablename__ = "dataset_records"
    __table_args__ = (
        Index("ix_records_dataset_fp", "dataset_id", "fingerprint"),
        Index("ix_records_import", "import_job_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    import_job_id: Mapped[int | None] = mapped_column(ForeignKey("import_jobs.id", ondelete="SET NULL"))
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based row in the source sheet (header = row 1)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict] = mapped_column(JSONType, nullable=False)
