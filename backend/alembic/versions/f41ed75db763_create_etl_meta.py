"""create_etl_meta

Revision ID: f41ed75db763
Revises: 8f5db224fc05
Create Date: 2026-05-14
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'f41ed75db763'
down_revision: Union[str, Sequence[str], None] = '8f5db224fc05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS etl_meta (
            id               SERIAL PRIMARY KEY,
            job_name         TEXT NOT NULL,
            run_at           TIMESTAMP NOT NULL,
            rows_processed   INTEGER,
            status           TEXT NOT NULL,
            error            TEXT,
            duration_seconds INTEGER
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS etl_meta")
