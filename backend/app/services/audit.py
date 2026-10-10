from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog
from app.services.context import RequestContext

log = logging.getLogger("app.audit")


def record(
    db: Session,
    ctx: RequestContext | None,
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: Any = None,
    details: dict | None = None,
    organization_id: int | None = None,
    actor_label: str | None = None,
) -> AuditLog:
    """Add an audit entry to the current transaction (the caller commits).

    Writing the audit row in the same transaction as the action guarantees that
    either both are persisted or neither is.
    """
    org_id = organization_id
    if org_id is None and ctx is not None and ctx.org is not None:
        org_id = ctx.org.id
    entry = AuditLog(
        organization_id=org_id,
        actor_user_id=ctx.user_id if ctx else None,
        actor_label=actor_label or (ctx.actor_label if ctx else "anonymous"),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details or {},
        ip_address=ctx.ip if ctx else None,
        request_id=ctx.request_id if ctx else None,
    )
    db.add(entry)
    log.info("audit", extra={"action": action, "entity_type": entity_type, "entity_id": entry.entity_id, "org": org_id})
    return entry
