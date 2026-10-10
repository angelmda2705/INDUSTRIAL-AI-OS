"""Database engine, session factory and tenant context propagation.

Tenant isolation is enforced in two layers:

1. Application layer: every tenant-owned model carries ``organization_id`` and
   all service queries go through :mod:`app.services.tenancy` helpers that add
   the filter and return 404 for rows belonging to another organization.
2. Database layer (PostgreSQL only): row-level security policies created by
   the Alembic migrations compare ``organization_id`` with the
   ``app.current_org_id`` setting. The setting is applied at the beginning of
   every transaction from ``session.info["org_id"]`` so that a missing
   application filter still cannot leak another tenant's rows.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import JSON, create_engine, event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

# JSONB on PostgreSQL, generic JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


def _make_engine(url: str, echo: bool = False) -> Engine:
    kwargs: dict = {"echo": echo, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()

    return engine


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        if settings.is_sqlite:
            from pathlib import Path

            db_path = settings.database_url.replace("sqlite:///", "", 1)
            if db_path and db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = _make_engine(settings.database_url, settings.database_echo)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)
    return _engine


def configure_engine(engine: Engine) -> None:
    """Replace the global engine (used by tests and CLI tools)."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()


_SET_TENANT_SQL = text("SELECT set_config('app.current_org_id', :org, true)")


@event.listens_for(Session, "after_begin")
def _apply_tenant_setting(session: Session, transaction, connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    org_id = session.info.get("org_id")
    connection.execute(_SET_TENANT_SQL, {"org": str(org_id) if org_id else ""})


def set_tenant(session: Session, org_id: int | None) -> None:
    """Bind the session to an organization for row-level security purposes."""
    session.info["org_id"] = org_id
    if session.in_transaction() and session.get_bind().dialect.name == "postgresql":
        session.execute(_SET_TENANT_SQL, {"org": str(org_id) if org_id else ""})
