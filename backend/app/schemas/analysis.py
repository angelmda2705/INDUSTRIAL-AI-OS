from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORM


class FindingOut(ORM):
    id: int
    code: str
    dataset_id: int | None
    area: str
    category: str
    nature: str
    title: str
    description: str
    rule_code: str
    method: str
    priority: str
    impact_amount: float | None
    impact_currency: str | None
    impact_basis: str | None
    confidence: str | None
    confidence_basis: str | None
    recommendation: str
    status: str
    owner_user_id: int | None
    due_date: date | None
    first_detected_at: datetime
    last_detected_at: datetime
    condition_active: bool
    last_analysis_run_id: int | None
    is_demo: bool


class FindingEventOut(ORM):
    id: int
    actor_label: str
    event_type: str
    from_status: str | None
    to_status: str | None
    note: str | None
    data: dict
    created_at: datetime


class FindingDetail(FindingOut):
    evidence: dict
    events: list[FindingEventOut]
    dataset_name: str | None = None
    owner_name: str | None = None


class FindingUpdate(BaseModel):
    status: Literal["open", "in_review", "action_planned", "resolved", "dismissed"] | None = None
    note: str | None = Field(None, max_length=5000)
    owner_user_id: int | None = None
    due_date: date | None = None


class CommentCreate(BaseModel):
    note: str = Field(min_length=1, max_length=5000)


class TargetIn(BaseModel):
    target_value: float
    tolerance: float = 0.0
    owner_label: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=2000)


class ReportCreate(BaseModel):
    report_type: Literal["diagnostic", "executive", "inventory", "maintenance", "logistics", "production"] = "diagnostic"
    file_format: Literal["pdf", "xlsx"] = "pdf"
    dataset_ids: list[int] | None = None
    include_demo: bool = True


class ReportOut(ORM):
    id: int
    report_type: str
    file_format: str
    title: str
    file_sha256: str
    file_size: int
    parameters: dict
    created_at: datetime


class AuditOut(ORM):
    id: int
    actor_label: str
    action: str
    entity_type: str | None
    entity_id: str | None
    details: dict
    ip_address: str | None
    request_id: str | None
    created_at: datetime
