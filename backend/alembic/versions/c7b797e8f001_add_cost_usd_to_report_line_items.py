"""add_cost_usd_to_report_line_items

Revision ID: c7b797e8f001
Revises: f41ed75db763
Create Date: 2026-05-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c7b797e8f001"
down_revision: Union[str, Sequence[str], None] = "f41ed75db763"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "report_line_items",
        sa.Column("cost_usd", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("report_line_items", "cost_usd")
