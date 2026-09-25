"""create_candidate_sources_table

Revision ID: f229223758bc
Revises: fd34c825c516
Create Date: 2026-09-24 22:44:50.943406

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f229223758bc'
down_revision: Union[str, Sequence[str], None] = 'fd34c825c516'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'candidate_sources',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('application_id', sa.Uuid(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('discovered_from', sa.String(length=500), nullable=True),
        sa.Column('discovery_depth', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='DISCOVERED', nullable=False),
        sa.Column('relevance', sa.String(length=100), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('last_inspected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_candidate_sources_application_id'), 'candidate_sources', ['application_id'], unique=False)
    op.create_index(op.f('ix_candidate_sources_status'), 'candidate_sources', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_candidate_sources_status'), table_name='candidate_sources')
    op.drop_index(op.f('ix_candidate_sources_application_id'), table_name='candidate_sources')
    op.drop_table('candidate_sources')

