"""Add RSI momentum factor columns to factor_daily table.

Revision ID: 007
Revises: 006
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add rsi_momentum and z_rsi_momentum columns to factor_daily."""
    with op.batch_alter_table("factor_daily") as batch_op:
        batch_op.add_column(sa.Column("rsi_momentum", sa.Float(), nullable=True,
                                       comment="RSI动量因子原始值 (RSI(5)-RSI(20))"))
        batch_op.add_column(sa.Column("z_rsi_momentum", sa.Float(), nullable=True,
                                       comment="RSI动量因子横截面Z-Score"))


def downgrade() -> None:
    """Remove RSI momentum columns from factor_daily."""
    with op.batch_alter_table("factor_daily") as batch_op:
        batch_op.drop_column("z_rsi_momentum")
        batch_op.drop_column("rsi_momentum")
