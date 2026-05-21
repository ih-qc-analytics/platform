"""set_unknown_reporting_base_currency

Revision ID: b4d7a9c2e101
Revises: a1c1b8a5d003
Create Date: 2026-05-21
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b4d7a9c2e101"
down_revision: Union[str, Sequence[str], None] = "a1c1b8a5d003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE report_payments
        ALTER COLUMN base_currency SET DEFAULT 'UNKNOWN'
    """)
    op.execute("""
        ALTER TABLE report_line_items
        ALTER COLUMN base_currency SET DEFAULT 'UNKNOWN'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE report_payments
        ALTER COLUMN base_currency SET DEFAULT 'MXN'
    """)
    op.execute("""
        ALTER TABLE report_line_items
        ALTER COLUMN base_currency SET DEFAULT 'MXN'
    """)
