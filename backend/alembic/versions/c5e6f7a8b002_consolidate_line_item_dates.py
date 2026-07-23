"""consolidate_line_item_dates

Removes the ambiguous date columns (payment_day, payment_date) and paid_total
revenue columns from report_line_items. Adds first_payment_date as the single
authoritative date for this table.

first_payment_date = MIN(allocation.payment_date) across all
report_payment_allocations rows for a given cart_product_id. It represents
the earliest date on which any payment was applied to this product, which is
the date the product's quantity "enters" a reporting period.

Revenue is now sourced exclusively from report_payment_allocations.

Revision ID: c5e6f7a8b002
Revises: c5e6f7a8b001
Create Date: 2026-07-20
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c5e6f7a8b002"
down_revision: Union[str, Sequence[str], None] = "c5e6f7a8b001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop indexes on removed columns before dropping columns
    op.execute("DROP INDEX IF EXISTS idx_rli_payment_date")

    # Remove stale date columns — replaced by first_payment_date
    op.execute("ALTER TABLE report_line_items DROP COLUMN IF EXISTS payment_day")
    op.execute("ALTER TABLE report_line_items DROP COLUMN IF EXISTS payment_date")

    # Remove revenue columns — revenue is now exclusively in report_payment_allocations
    op.execute("ALTER TABLE report_line_items DROP COLUMN IF EXISTS paid_total")
    op.execute("ALTER TABLE report_line_items DROP COLUMN IF EXISTS paid_total_mxn")
    op.execute("ALTER TABLE report_line_items DROP COLUMN IF EXISTS paid_total_usd")

    # Add single authoritative date column
    op.execute("ALTER TABLE report_line_items ADD COLUMN IF NOT EXISTS first_payment_date DATE")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rli_first_payment_date ON report_line_items (first_payment_date)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_rli_first_payment_date")
    op.execute("ALTER TABLE report_line_items DROP COLUMN IF EXISTS first_payment_date")

    op.execute(
        "ALTER TABLE report_line_items ADD COLUMN IF NOT EXISTS paid_total_usd DECIMAL(18,2)"
    )
    op.execute(
        "ALTER TABLE report_line_items ADD COLUMN IF NOT EXISTS paid_total_mxn DECIMAL(18,2)"
    )
    op.execute(
        "ALTER TABLE report_line_items ADD COLUMN IF NOT EXISTS paid_total DECIMAL(18,2) NOT NULL DEFAULT 0"
    )
    op.execute("ALTER TABLE report_line_items ADD COLUMN IF NOT EXISTS payment_date DATE")
    op.execute("ALTER TABLE report_line_items ADD COLUMN IF NOT EXISTS payment_day DATE")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rli_payment_date ON report_line_items (payment_date)"
    )
