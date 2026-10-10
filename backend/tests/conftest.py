"""Shared fixtures.

The suite runs on SQLite by default. Set ``IIOS_TEST_DATABASE_URL`` to a
PostgreSQL database (owned by a NON-superuser role) to run the same tests
against PostgreSQL, including the row-level-security tests.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="iios-tests-"))
os.environ.update(
    IIOS_ENVIRONMENT="test",
    IIOS_COOKIE_SECURE="false",
    IIOS_STORAGE_DIR=str(_TMP / "storage"),
    IIOS_LOG_JSON="false",
    IIOS_LOG_LEVEL="WARNING",
    IIOS_ALLOW_SELF_SIGNUP="true",
)
TEST_DB_URL = os.environ.get("IIOS_TEST_DATABASE_URL") or f"sqlite:///{_TMP / 'test.db'}"
os.environ["IIOS_DATABASE_URL"] = TEST_DB_URL

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core import config  # noqa: E402

config.get_settings.cache_clear()

from app.core.db import Base, _make_engine, configure_engine, session_factory, set_tenant  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.email import DEV_OUTBOX  # noqa: E402
from app.services.organizations import create_organization  # noqa: E402

IS_PG = TEST_DB_URL.startswith("postgresql")
PASSWORD = "Prueba-Segura-2024"


def _prepare_schema(engine) -> None:
    if IS_PG:
        from alembic.config import Config

        from alembic import command

        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
    else:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)


@pytest.fixture(scope="session")
def engine():
    eng = _make_engine(TEST_DB_URL)
    _prepare_schema(eng)
    configure_engine(eng)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def clean_db(engine):
    """Empty every table (except the seeded plans) before each test."""
    limiter.reset()
    DEV_OUTBOX.clear()
    tables = [t.name for t in reversed(Base.metadata.sorted_tables) if t.name != "plans"]
    with engine.begin() as conn:
        if IS_PG:
            conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        else:
            for t in tables:
                conn.execute(text(f"DELETE FROM {t}"))
    if not IS_PG:
        with session_factory()() as db:
            from app.services.organizations import ensure_default_plans

            ensure_default_plans(db)
            db.commit()
    yield


@pytest.fixture
def db(engine):
    s = session_factory()()
    yield s
    s.close()


@pytest.fixture(scope="session")
def app(engine):
    return create_app()


class ApiClient:
    """TestClient wrapper that keeps the CSRF header after login."""

    def __init__(self, app):
        self.c = TestClient(app, base_url="http://testserver")
        self.me = None

    def login(self, email: str, password: str = PASSWORD, organization_id: int | None = None):
        r = self.c.post("/api/v1/auth/login", json={"email": email, "password": password, "organization_id": organization_id})
        if r.status_code == 200:
            self.c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
            self.me = r.json()["me"]
        return r

    def __getattr__(self, name):
        return getattr(self.c, name)


@pytest.fixture
def make_client(app):
    def factory() -> ApiClient:
        return ApiClient(app)

    return factory


def create_org_with_admin(db, name: str, email: str, plan: str = "professional"):
    org, user = create_organization(db, name=name, admin_email=email, admin_name=name + " Admin",
                                    admin_password=PASSWORD, plan_code=plan)
    db.commit()
    set_tenant(db, None)
    return org, user


@pytest.fixture
def org_a(db):
    return create_org_with_admin(db, "Empresa A", "admin@a.test")


@pytest.fixture
def org_b(db):
    return create_org_with_admin(db, "Empresa B", "admin@b.test")


@pytest.fixture
def admin_a(make_client, org_a):
    client = make_client()
    assert client.login("admin@a.test").status_code == 200
    return client


@pytest.fixture
def admin_b(make_client, org_b):
    client = make_client()
    assert client.login("admin@b.test").status_code == 200
    return client


def add_user(admin_client: ApiClient, email: str, role: str) -> None:
    r = admin_client.post("/api/v1/organization/members",
                          json={"email": email, "display_name": email.split("@")[0], "role": role, "initial_password": PASSWORD})
    assert r.status_code == 201, r.text


def login_member(make_client, email: str) -> ApiClient:
    """Log in a user created with a temporary password and complete the mandatory change."""
    client = make_client()
    assert client.login(email).status_code == 200
    r = client.post("/api/v1/auth/change-password", json={"current_password": PASSWORD, "new_password": PASSWORD + "x"})
    assert r.status_code == 200, r.text
    return client


def upload_csv(client: ApiClient, content: str, filename: str = "datos.csv"):
    return client.post("/api/v1/imports", files={"file": (filename, content.encode("utf-8"), "text/csv")})


def import_csv(client: ApiClient, content: str, template: str, dataset_name: str, mapping: dict | None = None,
               dataset_id: int | None = None, **commit_opts) -> dict:
    """Run the whole import workflow and return the commit response JSON."""
    r = upload_csv(client, content)
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    preview = client.get(f"/api/v1/imports/{job_id}/preview").json()
    body = {"template_code": template, "mapping": mapping or preview["suggested_mappings"].get(template, {})}
    if dataset_id:
        body["dataset_id"] = dataset_id
    else:
        body["dataset_name"] = dataset_name
    r = client.post(f"/api/v1/imports/{job_id}/validate", json=body)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/imports/{job_id}/commit", json={"skip_invalid": True, "skip_duplicates": True, **commit_opts})
    assert r.status_code == 200, r.text
    return r.json()

