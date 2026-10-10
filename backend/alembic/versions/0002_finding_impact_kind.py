"""finding impact kind

Separates the meaning of a finding's economic amount (recorded cost, estimated
excess cost, immobilized capital) so amounts of different kinds are never added.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10 02:11:21.164082
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKFILL = {
    "recorded_cost": ["MNT-RECURRENT-FAILURES"],
    "capital_tied": ["INV-EXCESS", "INV-NO-MOVEMENT"],
    "estimated_excess_cost": ["FLT-FUEL-ANOMALY"],
}


def upgrade() -> None:
    with op.batch_alter_table('findings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('impact_kind', sa.String(length=30), nullable=True))

    is_pg = op.get_bind().dialect.name == "postgresql"
    if is_pg:
        # Data migrations run without a tenant context; RLS is FORCEd for the owner,
        # so it is lifted only for the duration of this transaction.
        op.execute("ALTER TABLE findings NO FORCE ROW LEVEL SECURITY")
    stmt = sa.text(
        "UPDATE findings SET impact_kind = :kind WHERE impact_amount IS NOT NULL AND rule_code IN :rules"
    ).bindparams(sa.bindparam("rules", expanding=True))
    for kind, rules in BACKFILL.items():
        op.get_bind().execute(stmt, {"kind": kind, "rules": rules})
    if is_pg:
        op.execute("ALTER TABLE findings FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    with op.batch_alter_table('findings', schema=None) as batch_op:
        batch_op.drop_column('impact_kind')
