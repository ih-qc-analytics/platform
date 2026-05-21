"""create_report_line_items

Revision ID: a1c1b8a5d002
Revises: a1c1b8a5d001
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1c1b8a5d002"
down_revision: Union[str, Sequence[str], None] = "a1c1b8a5d001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS report_line_items (
            id                          SERIAL PRIMARY KEY,
            cart_product_id             INTEGER NOT NULL,
            etl_date                    DATE NOT NULL,
            seller_id                   INTEGER NOT NULL,
            seller_name                 TEXT NOT NULL,
            lead_id                     INTEGER NOT NULL,
            school_name                 TEXT,
            site                        TEXT,
            zone_name                   TEXT,
            state_name                  TEXT,
            city                        TEXT,
            all_states                  TEXT[] NOT NULL DEFAULT '{}'::text[],
            all_cities                  TEXT[] NOT NULL DEFAULT '{}'::text[],
            state_names                 TEXT[] NOT NULL DEFAULT '{}'::text[],
            city_names                  TEXT[] NOT NULL DEFAULT '{}'::text[],
            year                        INTEGER NOT NULL,
            month                       INTEGER NOT NULL,
            created_at                  TIMESTAMP NOT NULL,
            payment_date                DATE,
            payment_day                 DATE,
            base_currency               TEXT NOT NULL DEFAULT 'MXN',
            cart_id                     INTEGER NOT NULL,
            product_id                  INTEGER NOT NULL,
            product_type                TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            exam_cat_name               TEXT,
            exam_category               TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            exam_canonical_name         TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            exam_date_type              TEXT,
            billing_status              TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            payment_status              TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            business_status             TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            is_active                   BOOLEAN NOT NULL DEFAULT TRUE,
            include_in_product_breakdown BOOLEAN NOT NULL DEFAULT TRUE,
            quantity                    INTEGER NOT NULL DEFAULT 0,
            expected_total              DECIMAL(18,2) NOT NULL DEFAULT 0,
            expected_cost               DECIMAL(18,2) NOT NULL DEFAULT 0,
            discount                    DECIMAL(18,2),
            book_commission             DECIMAL(18,2),
            exam_commission             DECIMAL(18,2),
            expected_total_mxn          DECIMAL(18,2),
            expected_total_usd          DECIMAL(18,2),
            expected_cost_mxn           DECIMAL(18,2),
            expected_cost_usd           DECIMAL(18,2),
            paid_total                  DECIMAL(18,2) NOT NULL DEFAULT 0,
            paid_total_mxn              DECIMAL(18,2),
            paid_total_usd              DECIMAL(18,2),
            student_count               INTEGER NOT NULL DEFAULT 0,
            payment_count               INTEGER NOT NULL DEFAULT 0,
            total                       DECIMAL(18,2),
            cost                        DECIMAL(18,2),
            total_mxn                   DECIMAL(18,2),
            total_usd                   DECIMAL(18,2),
            cost_mxn                    DECIMAL(18,2),
            cost_usd                    DECIMAL(18,2),
            CONSTRAINT uq_cart_product UNIQUE (cart_product_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_year         ON report_line_items (year)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_month        ON report_line_items (month)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_site         ON report_line_items (site)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_zone         ON report_line_items (zone_name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_seller       ON report_line_items (seller_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_lead         ON report_line_items (lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_cart         ON report_line_items (cart_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_product_type ON report_line_items (product_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_exam_cat     ON report_line_items (exam_category)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_exam_name    ON report_line_items (exam_canonical_name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_created_at   ON report_line_items (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_payment_date ON report_line_items (payment_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_seller_year  ON report_line_items (seller_id, year)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_site_year    ON report_line_items (site, year)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_year_product ON report_line_items (year, product_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_payment_stat ON report_line_items (payment_status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_active       ON report_line_items (is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_include_pd   ON report_line_items (include_in_product_breakdown)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_rli_search ON report_line_items
        USING gin(to_tsvector('spanish', coalesce(seller_name,'') || ' ' || coalesce(school_name,'')))
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_state_names_gin ON report_line_items USING gin (state_names)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rli_city_names_gin ON report_line_items USING gin (city_names)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS report_line_items")
