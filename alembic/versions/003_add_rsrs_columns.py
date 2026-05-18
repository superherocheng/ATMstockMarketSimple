"""Add RSRS columns to factor_daily table.

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    """Add rsrs and z_rsrs columns to factor_daily."""
    with op.batch_alter_table("factor_daily") as batch_op:
        batch_op.add_column(sa.Column("rsrs", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("z_rsrs", sa.Float(), nullable=True))


def downgrade():
    """Remove rsrs and z_rsrs columns from factor_daily."""
    with op.batch_alter_table("factor_daily") as batch_op:
        batch_op.drop_column("z_rsrs")
        batch_op.drop_column("rsrs")
