"""create_report_line_items

Revision ID: 291b0f8d9562
Revises:
Create Date: 2026-05-14
"""
from typing import Sequence, Union
from alembic import op

revision: str = '291b0f8d9562'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS report_line_items (
            id                      SERIAL PRIMARY KEY,
            cart_product_id         INTEGER NOT NULL,
            etl_date                DATE NOT NULL,
            seller_id               INTEGER NOT NULL,
            seller_name             TEXT NOT NULL,
            lead_id                 INTEGER NOT NULL,
            school_name             TEXT,
            site                    TEXT,
            zone_name               TEXT,
            state_name              TEXT,
            city                    TEXT,
            business_status         TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            cart_id                 INTEGER NOT NULL,
            created_at              TIMESTAMP NOT NULL,
            year                    INTEGER NOT NULL,
            month                   INTEGER NOT NULL,
            payment_status          TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            payment_date            DATE,
            billing_status          TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            product_id              INTEGER NOT NULL,
            product_type            TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            exam_cat_name           TEXT,
            exam_category           TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            exam_canonical_name     TEXT NOT NULL DEFAULT 'UNCATEGORIZED',
            exam_date_type          TEXT,
            quantity                INTEGER NOT NULL DEFAULT 0,
            total                   DECIMAL(10,2) NOT NULL DEFAULT 0,
            cost                    DECIMAL(10,2) NOT NULL DEFAULT 0,
            discount                DECIMAL(10,2),
            book_commission         DECIMAL(10,2),
            exam_commission         DECIMAL(10,2),
            base_currency           TEXT NOT NULL DEFAULT 'MXN',
            total_mxn               DECIMAL(10,2),
            total_usd               DECIMAL(10,2),
            is_active               BOOLEAN NOT NULL DEFAULT TRUE,
            CONSTRAINT uq_cart_product UNIQUE (cart_product_id)
        )
    """)

    # Single-column indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_year            ON report_line_items (year)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_month           ON report_line_items (month)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_site            ON report_line_items (site)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_zone            ON report_line_items (zone_name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_seller          ON report_line_items (seller_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lead            ON report_line_items (lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_type    ON report_line_items (product_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_exam_category   ON report_line_items (exam_category)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_exam_name       ON report_line_items (exam_canonical_name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payment_status  ON report_line_items (payment_status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_is_active       ON report_line_items (is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_business_status ON report_line_items (business_status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_created_at      ON report_line_items (created_at)")

    # Composite indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_seller_year    ON report_line_items (seller_id, year)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_site_year      ON report_line_items (site, year)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payment_active ON report_line_items (payment_status, is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_year_product   ON report_line_items (year, product_type)")

    # Full text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_search ON report_line_items
        USING gin(to_tsvector('spanish', coalesce(seller_name,'') || ' ' || coalesce(school_name,'')))
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS report_line_items")
