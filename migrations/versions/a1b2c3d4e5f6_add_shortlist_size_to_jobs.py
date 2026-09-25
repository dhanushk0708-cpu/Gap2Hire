"""add_shortlist_size_to_jobs

Revision ID: a1b2c3d4e5f6
Revises: 5e9c1b3f7a2d
Create Date: 2026-09-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5e9c1b3f7a2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'jobs',
        sa.Column('shortlist_size', sa.Integer(), server_default='5', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('jobs', 'shortlist_size')
