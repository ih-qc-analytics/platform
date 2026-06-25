"""create_report_payment_allocations

Revision ID: a1c1b8a5d003
Revises: a1c1b8a5d002
Create Date: 2026-05-18
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a1c1b8a5d003"
down_revision: Union[str, Sequence[str], None] = "a1c1b8a5d002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS report_payment_allocations (
            id                      SERIAL PRIMARY KEY,
            payment_id              INTEGER NOT NULL,
            cart_product_id         INTEGER NOT NULL,
            etl_date                DATE NOT NULL,
            allocated_amount        DECIMAL(18,2) NOT NULL DEFAULT 0,
            allocated_amount_mxn    DECIMAL(18,2),
            allocated_amount_usd    DECIMAL(18,2),
            CONSTRAINT uq_payment_cart_product UNIQUE (payment_id, cart_product_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rpa_payment      ON report_payment_allocations (payment_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rpa_cart_product ON report_payment_allocations (cart_product_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS report_payment_allocations")
