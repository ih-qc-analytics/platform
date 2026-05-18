"""Merge multiple heads

Revision ID: 3409ee38218c
Revises: 26ac394e66b8, c7b797e8f001
Create Date: 2026-05-17 18:14:58.365521

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3409ee38218c'
down_revision: Union[str, Sequence[str], None] = ('26ac394e66b8', 'c7b797e8f001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
