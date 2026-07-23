"""extend_report_payment_allocations

Adds payment_date and dimension columns so allocation rows are self-contained
for reporting queries (no join to line_items needed at read time).

Revision ID: c5e6f7a8b001
Revises: b4d7a9c2e101
Create Date: 2026-07-20
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c5e6f7a8b001"
down_revision: Union[str, Sequence[str], None] = "b4d7a9c2e101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE report_payment_allocations ADD COLUMN IF NOT EXISTS payment_date DATE")
    op.execute("ALTER TABLE report_payment_allocations ADD COLUMN IF NOT EXISTS seller_id INTEGER")
    op.execute("ALTER TABLE report_payment_allocations ADD COLUMN IF NOT EXISTS seller_name TEXT")
    op.execute("ALTER TABLE report_payment_allocations ADD COLUMN IF NOT EXISTS lead_id INTEGER")
    op.execute("ALTER TABLE report_payment_allocations ADD COLUMN IF NOT EXISTS site TEXT")
    op.execute("ALTER TABLE report_payment_allocations ADD COLUMN IF NOT EXISTS product_type TEXT")
    op.execute(
        "ALTER TABLE report_payment_allocations ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rpa_payment_date       ON report_payment_allocations (payment_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rpa_date_active_seller ON report_payment_allocations (payment_date, is_active, seller_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rpa_site               ON report_payment_allocations (site)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rpa_product_type       ON report_payment_allocations (product_type)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_rpa_product_type")
    op.execute("DROP INDEX IF EXISTS idx_rpa_site")
    op.execute("DROP INDEX IF EXISTS idx_rpa_date_active_seller")
    op.execute("DROP INDEX IF EXISTS idx_rpa_payment_date")
    op.execute("ALTER TABLE report_payment_allocations DROP COLUMN IF EXISTS is_active")
    op.execute("ALTER TABLE report_payment_allocations DROP COLUMN IF EXISTS product_type")
    op.execute("ALTER TABLE report_payment_allocations DROP COLUMN IF EXISTS site")
    op.execute("ALTER TABLE report_payment_allocations DROP COLUMN IF EXISTS lead_id")
    op.execute("ALTER TABLE report_payment_allocations DROP COLUMN IF EXISTS seller_name")
    op.execute("ALTER TABLE report_payment_allocations DROP COLUMN IF EXISTS seller_id")
    op.execute("ALTER TABLE report_payment_allocations DROP COLUMN IF EXISTS payment_date")
