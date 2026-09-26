"""create interview integrity events table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-26 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'interview_integrity_events',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('interview_session_id', sa.UUID(), sa.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False, index=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_interview_integrity_events_occurred_at', 'interview_integrity_events', ['occurred_at'], if_not_exists=True)


def downgrade() -> None:
    op.drop_table('interview_integrity_events')
