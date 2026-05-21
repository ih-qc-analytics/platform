"""create_exchange_rates

Revision ID: 8f5db224fc05
Revises:
Create Date: 2026-05-14
"""
from typing import Sequence, Union
from alembic import op

revision: str = '8f5db224fc05'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id              SERIAL PRIMARY KEY,
            date            DATE NOT NULL,
            from_currency   TEXT NOT NULL,
            to_currency     TEXT NOT NULL,
            rate            DECIMAL(18, 8) NOT NULL,
            CONSTRAINT uq_rate UNIQUE (date, from_currency, to_currency)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_rate_lookup
        ON exchange_rates (date, from_currency, to_currency)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS exchange_rates")
