from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORM


class ImportJobOut(ORM):
    id: int
    original_filename: str
    file_type: str
    file_size: int
    file_sha256: str
    status: str
    sheet_names: list
    sheet_name: str | None
    detected_columns: list
    total_rows: int
    template_code: str | None
    column_mapping: dict
    parse_options: dict
    target_dataset_id: int | None
    target_dataset_name: str | None
    validation_summary: dict
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    imported_rows: int
    created_at: datetime
    committed_at: datetime | None
    reverted_at: datetime | None
    is_demo: bool


class ValidateRequest(BaseModel):
    template_code: str
    mapping: dict[str, str] = Field(default_factory=dict)
    dataset_id: int | None = None
    dataset_name: str | None = Field(None, max_length=160)
    sheet_name: str | None = None
    decimal_separator: str | None = None
    date_format: str | None = None


class CommitRequest(BaseModel):
    skip_invalid: bool = True
    skip_duplicates: bool = True
    dataset_description: str | None = Field(None, max_length=2000)
    run_analysis: bool = True


class DatasetOut(ORM):
    id: int
    name: str
    description: str | None
    template_code: str
    is_demo: bool
    row_count: int
    created_at: datetime
    last_analyzed_at: datetime | None
    analysis_stale: bool


class AnalysisRunOut(ORM):
    id: int
    dataset_id: int
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    record_count: int
    period_start: date | None
    period_end: date | None
    summary: dict
    error_message: str | None


class RecordOut(ORM):
    id: int
    source_row: int
    import_job_id: int | None
    data: dict
