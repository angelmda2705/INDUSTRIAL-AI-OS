"""Schema/migration consistency and PostgreSQL row-level security."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.db import session_factory, set_tenant
from app.models import Dataset, tenant_tables
from tests.conftest import IS_PG, create_org_with_admin

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0001_initial_schema.py"


def test_migration_tenant_table_list_matches_models():
    spec = importlib.util.spec_from_file_location("m0001", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert sorted(module.TENANT_TABLES) == tenant_tables()


def test_every_tenant_table_has_organization_id(engine):
    from app.core.db import Base

    for name in tenant_tables():
        assert "organization_id" in Base.metadata.tables[name].c


def test_migrations_match_models_on_sqlite(tmp_path):
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    from alembic import command
    from app.core.db import Base

    eng = create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    cfg = Config(str(MIGRATION.parents[2] / "alembic.ini"))
    with eng.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diff == [], diff
        assert conn.execute(text("SELECT count(*) FROM plans")).scalar() == 3
    with eng.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, "base")


@pytest.mark.skipif(not IS_PG, reason="row-level security only exists on PostgreSQL")
class TestRowLevelSecurity:
    @pytest.fixture
    def two_orgs(self, db):
        a, _ = create_org_with_admin(db, "RLS A", "rls@a.test")
        b, _ = create_org_with_admin(db, "RLS B", "rls@b.test")
        for org, name in ((a, "datos A"), (b, "datos B")):
            set_tenant(db, org.id)
            db.add(Dataset(organization_id=org.id, name=name, template_code="generic"))
            db.commit()
        set_tenant(db, None)
        return a, b

    def test_role_is_not_superuser(self, db):
        row = db.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
        assert row == (False, False), "tests must run with a non-superuser role or RLS is bypassed"

    def test_queries_without_filter_only_see_current_tenant(self, two_orgs):
        a, b = two_orgs
        with session_factory()() as s:
            set_tenant(s, a.id)
            names = [d.name for d in s.execute(select(Dataset)).scalars()]  # no WHERE clause on purpose
            assert names == ["datos A"]
            assert s.execute(text("SELECT count(*) FROM datasets")).scalar() == 1

    def test_no_tenant_means_no_rows(self, two_orgs):
        with session_factory()() as s:
            set_tenant(s, None)
            assert s.execute(text("SELECT count(*) FROM datasets")).scalar() == 0

    def test_cannot_write_into_other_tenant(self, two_orgs):
        a, b = two_orgs
        with session_factory()() as s:
            set_tenant(s, a.id)
            s.add(Dataset(organization_id=b.id, name="intrusión", template_code="generic"))
            with pytest.raises(DBAPIError):
                s.commit()

    def test_cannot_update_or_delete_other_tenant(self, two_orgs):
        a, b = two_orgs
        with session_factory()() as s:
            set_tenant(s, a.id)
            assert s.execute(text("UPDATE datasets SET name = 'x' WHERE organization_id = :b"), {"b": b.id}).rowcount == 0
            assert s.execute(text("DELETE FROM datasets WHERE organization_id = :b"), {"b": b.id}).rowcount == 0
            s.commit()

    def test_setting_survives_commit(self, two_orgs):
        a, _ = two_orgs
        with session_factory()() as s:
            set_tenant(s, a.id)
            s.commit()  # a new transaction must re-apply the tenant setting
            assert s.execute(text("SELECT count(*) FROM datasets")).scalar() == 1
