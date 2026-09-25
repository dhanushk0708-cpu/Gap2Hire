"""create_research_state_tables

Revision ID: 5e9c1b3f7a2d
Revises: 8c4f9a12b3e5
Create Date: 2026-09-24 23:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e9c1b3f7a2d'
down_revision: Union[str, Sequence[str], None] = '8c4f9a12b3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create research_sessions, research_capability_states, and research_events tables."""
    # 1. research_sessions
    op.create_table(
        'research_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('application_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='PENDING', nullable=False),
        sa.Column('current_source_id', sa.Uuid(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('stop_reason', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['current_source_id'], ['candidate_sources.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_research_sessions_application_id'), 'research_sessions', ['application_id'], unique=False)
    op.create_index(op.f('ix_research_sessions_status'), 'research_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_research_sessions_current_source_id'), 'research_sessions', ['current_source_id'], unique=False)

    # 2. research_capability_states
    op.create_table(
        'research_capability_states',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('research_session_id', sa.Uuid(), nullable=False),
        sa.Column('capability_id', sa.Uuid(), nullable=False),
        sa.Column('state', sa.String(length=50), server_default='UNKNOWN', nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['capability_id'], ['capabilities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['research_session_id'], ['research_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('research_session_id', 'capability_id', name='uq_research_session_capability'),
    )
    op.create_index(op.f('ix_research_capability_states_research_session_id'), 'research_capability_states', ['research_session_id'], unique=False)
    op.create_index(op.f('ix_research_capability_states_capability_id'), 'research_capability_states', ['capability_id'], unique=False)
    op.create_index(op.f('ix_research_capability_states_state'), 'research_capability_states', ['state'], unique=False)

    # 3. research_events
    op.create_table(
        'research_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('research_session_id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('source_id', sa.Uuid(), nullable=True),
        sa.Column('capability_id', sa.Uuid(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['capability_id'], ['capabilities.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['research_session_id'], ['research_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['candidate_sources.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_research_events_research_session_id'), 'research_events', ['research_session_id'], unique=False)
    op.create_index(op.f('ix_research_events_event_type'), 'research_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_research_events_source_id'), 'research_events', ['source_id'], unique=False)
    op.create_index(op.f('ix_research_events_capability_id'), 'research_events', ['capability_id'], unique=False)
    op.create_index(op.f('ix_research_events_created_at'), 'research_events', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema: drop research_events, research_capability_states, and research_sessions tables."""
    op.drop_index(op.f('ix_research_events_created_at'), table_name='research_events')
    op.drop_index(op.f('ix_research_events_capability_id'), table_name='research_events')
    op.drop_index(op.f('ix_research_events_source_id'), table_name='research_events')
    op.drop_index(op.f('ix_research_events_event_type'), table_name='research_events')
    op.drop_index(op.f('ix_research_events_research_session_id'), table_name='research_events')
    op.drop_table('research_events')

    op.drop_index(op.f('ix_research_capability_states_state'), table_name='research_capability_states')
    op.drop_index(op.f('ix_research_capability_states_capability_id'), table_name='research_capability_states')
    op.drop_index(op.f('ix_research_capability_states_research_session_id'), table_name='research_capability_states')
    op.drop_table('research_capability_states')

    op.drop_index(op.f('ix_research_sessions_current_source_id'), table_name='research_sessions')
    op.drop_index(op.f('ix_research_sessions_status'), table_name='research_sessions')
    op.drop_index(op.f('ix_research_sessions_application_id'), table_name='research_sessions')
    op.drop_table('research_sessions')
