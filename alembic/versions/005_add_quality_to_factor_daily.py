"""Add financial quality columns to factor_daily table.

Revision ID: 005
Revises: 004
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add f_quality and z_quality columns to factor_daily."""
    with op.batch_alter_table("factor_daily") as batch_op:
        batch_op.add_column(sa.Column("f_quality", sa.Float(), nullable=True,
                                       comment="Raw financial quality factor value"))
        batch_op.add_column(sa.Column("z_quality", sa.Float(), nullable=True,
                                       comment="Cross-sectional Z-scored quality factor"))


def downgrade() -> None:
    """Remove quality columns from factor_daily."""
    with op.batch_alter_table("factor_daily") as batch_op:
        batch_op.drop_column("z_quality")
        batch_op.drop_column("f_quality")
