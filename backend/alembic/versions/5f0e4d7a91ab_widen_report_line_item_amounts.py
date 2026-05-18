"""widen_report_line_item_amounts

Revision ID: 5f0e4d7a91ab
Revises: 3409ee38218c
Create Date: 2026-05-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "5f0e4d7a91ab"
down_revision: Union[str, Sequence[str], None] = "3409ee38218c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WIDE_NUMERIC = sa.Numeric(15, 2)
NARROW_NUMERIC = sa.Numeric(10, 2)


def upgrade() -> None:
    for column_name, nullable in (
        ("total", False),
        ("cost", False),
        ("discount", True),
        ("book_commission", True),
        ("exam_commission", True),
        ("total_mxn", True),
        ("cost_mxn", True),
        ("total_usd", True),
        ("cost_usd", True),
    ):
        op.alter_column(
            "report_line_items",
            column_name,
            existing_type=NARROW_NUMERIC,
            type_=WIDE_NUMERIC,
            existing_nullable=nullable,
        )


def downgrade() -> None:
    for column_name, nullable in (
        ("total", False),
        ("cost", False),
        ("discount", True),
        ("book_commission", True),
        ("exam_commission", True),
        ("total_mxn", True),
        ("cost_mxn", True),
        ("total_usd", True),
        ("cost_usd", True),
    ):
        op.alter_column(
            "report_line_items",
            column_name,
            existing_type=WIDE_NUMERIC,
            type_=NARROW_NUMERIC,
            existing_nullable=nullable,
        )
