"""add_cost_mxn_to_report_line_items

Revision ID: 26ac394e66b8
Revises: f41ed75db763
Create Date: 2026-05-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '26ac394e66b8'
down_revision: Union[str, Sequence[str], None] = 'f41ed75db763'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "report_line_items",
        sa.Column("cost_mxn", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("report_line_items", "cost_mxn")
