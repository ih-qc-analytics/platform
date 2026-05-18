"""add reporting breakdown and geo fields

Revision ID: 9c9e3b3d8d52
Revises: 5f0e4d7a91ab
Create Date: 2026-05-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9c9e3b3d8d52"
down_revision: Union[str, Sequence[str], None] = "5f0e4d7a91ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("report_line_items", sa.Column("payment_day", sa.Date(), nullable=True))
    op.add_column(
        "report_line_items",
        sa.Column(
            "include_in_product_breakdown",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
    )
    op.add_column(
        "report_line_items",
        sa.Column(
            "state_names",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    op.add_column(
        "report_line_items",
        sa.Column(
            "city_names",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )

    op.execute("""
        UPDATE report_line_items
        SET
            payment_day = COALESCE(payment_date, DATE(created_at)),
            state_names = CASE
                WHEN state_name IS NULL OR state_name = '' THEN '{}'::text[]
                ELSE ARRAY[state_name]
            END,
            city_names = CASE
                WHEN city IS NULL OR city = '' THEN '{}'::text[]
                ELSE ARRAY[city]
            END
    """)
    op.create_index("idx_payment_day", "report_line_items", ["payment_day"], unique=False)
    op.create_index(
        "idx_state_names_gin",
        "report_line_items",
        ["state_names"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "idx_city_names_gin",
        "report_line_items",
        ["city_names"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("idx_city_names_gin", table_name="report_line_items")
    op.drop_index("idx_state_names_gin", table_name="report_line_items")
    op.drop_index("idx_payment_day", table_name="report_line_items")
    op.drop_column("report_line_items", "city_names")
    op.drop_column("report_line_items", "state_names")
    op.drop_column("report_line_items", "include_in_product_breakdown")
    op.drop_column("report_line_items", "payment_day")
