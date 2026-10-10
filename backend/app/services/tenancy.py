"""Tenant-scoped data access helpers.

Every lookup of a tenant-owned row by id must use :func:`get_owned` so that a
row from another organization is reported as *not found* (not *forbidden*),
which avoids confirming that the id exists.
"""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.services.context import RequestContext

T = TypeVar("T")


def scoped(model: type[T], ctx: RequestContext) -> Select:
    return select(model).where(model.organization_id == ctx.org_id)  # type: ignore[attr-defined]


def get_owned(db: Session, model: type[T], obj_id: int, ctx: RequestContext, label: str = "Registro") -> T:
    obj = db.execute(
        select(model).where(model.id == obj_id, model.organization_id == ctx.org_id)  # type: ignore[attr-defined]
    ).scalar_one_or_none()
    if obj is None:
        raise NotFound(f"{label} no encontrado.")
    return obj
