"""add_candidate_source_id_to_evidence

Revision ID: 8c4f9a12b3e5
Revises: f229223758bc
Create Date: 2026-09-24 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c4f9a12b3e5'
down_revision: Union[str, Sequence[str], None] = 'f229223758bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add nullable candidate_source_id foreign key to evidence table."""
    op.add_column(
        'evidence',
        sa.Column('candidate_source_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_evidence_candidate_source_id',
        'evidence',
        'candidate_sources',
        ['candidate_source_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        op.f('ix_evidence_candidate_source_id'),
        'evidence',
        ['candidate_source_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema: remove candidate_source_id from evidence table."""
    op.drop_index(op.f('ix_evidence_candidate_source_id'), table_name='evidence')
    op.drop_constraint('fk_evidence_candidate_source_id', 'evidence', type_='foreignkey')
    op.drop_column('evidence', 'candidate_source_id')
