"""create_report_payments

Revision ID: a1c1b8a5d001
Revises: f41ed75db763
Create Date: 2026-05-18
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a1c1b8a5d001"
down_revision: Union[str, Sequence[str], None] = "f41ed75db763"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS report_payments (
            id                  SERIAL PRIMARY KEY,
            payment_id          INTEGER NOT NULL,
            etl_date            DATE NOT NULL,
            seller_id           INTEGER NOT NULL,
            seller_name         TEXT NOT NULL,
            lead_id             INTEGER NOT NULL,
            school_name         TEXT,
            site                TEXT,
            zone_name           TEXT,
            state_name          TEXT,
            city                TEXT,
            all_states          TEXT[] NOT NULL DEFAULT '{}'::text[],
            all_cities          TEXT[] NOT NULL DEFAULT '{}'::text[],
            state_names         TEXT[] NOT NULL DEFAULT '{}'::text[],
            city_names          TEXT[] NOT NULL DEFAULT '{}'::text[],
            year                INTEGER NOT NULL,
            month               INTEGER NOT NULL,
            created_at          TIMESTAMP NOT NULL,
            payment_date        DATE,
            base_currency       TEXT NOT NULL DEFAULT 'MXN',
            cart_id             INTEGER NOT NULL,
            payment_status      TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            business_status     TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            is_active           BOOLEAN NOT NULL DEFAULT TRUE,
            amount              DECIMAL(18,2) NOT NULL DEFAULT 0,
            amount_mxn          DECIMAL(18,2),
            amount_usd          DECIMAL(18,2),
            CONSTRAINT uq_payment UNIQUE (payment_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_rp_year           ON report_payments (year)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rp_month          ON report_payments (month)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rp_site           ON report_payments (site)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rp_zone           ON report_payments (zone_name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rp_seller         ON report_payments (seller_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rp_lead           ON report_payments (lead_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rp_payment_status ON report_payments (payment_status)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_rp_is_active      ON report_payments (is_active)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rp_business       ON report_payments (business_status)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_rp_created_at     ON report_payments (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rp_payment_date   ON report_payments (payment_date)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rp_payment_active ON report_payments (payment_status, is_active)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_rp_site_year      ON report_payments (site, year)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rp_seller_year    ON report_payments (seller_id, year)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS report_payments")
