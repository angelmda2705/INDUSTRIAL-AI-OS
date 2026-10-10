from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, JSONType
from app.models.base import TimestampMixin

ALL_MODULES = ["imports", "analytics", "findings", "reports", "kpis"]


class Plan(Base, TimestampMixin):
    """Commercial plan. Billing is out of scope for now; the plan only carries limits and modules."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # e.g. {"max_users": 10, "max_imports_per_month": 50, "max_rows_per_import": 50000}
    limits: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    modules: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    plan_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("plans.id", ondelete="SET NULL"))
    # Overrides of the plan's module list (None = use plan modules).
    enabled_modules: Mapped[list | None] = mapped_column(JSONType)
    # Organization-level configuration (currency, timezone, analysis parameters...)
    settings: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    plan: Mapped[Plan | None] = relationship(lazy="joined")

    @property
    def modules(self) -> list[str]:
        if self.enabled_modules is not None:
            return list(self.enabled_modules)
        if self.plan is not None:
            return list(self.plan.modules)
        return list(ALL_MODULES)

    @property
    def limits(self) -> dict:
        return dict(self.plan.limits) if self.plan else {}
