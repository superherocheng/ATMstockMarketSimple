"""Add intraday efficiency columns to factor_daily table.

Revision ID: 006
Revises: 005
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add intraday_efficiency and z_efficiency columns to factor_daily."""
    with op.batch_alter_table("factor_daily") as batch_op:
        batch_op.add_column(sa.Column("intraday_eff", sa.Float(), nullable=True,
                                       comment="日内价格效率因子原始值 (EWMA差)"))
        batch_op.add_column(sa.Column("z_efficiency", sa.Float(), nullable=True,
                                       comment="日内效率因子横截面Z-Score"))


def downgrade() -> None:
    """Remove efficiency columns from factor_daily."""
    with op.batch_alter_table("factor_daily") as batch_op:
        batch_op.drop_column("z_efficiency")
        batch_op.drop_column("intraday_eff")
