"""create interview schedules table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-26 13:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'interview_schedules',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('session_id', sa.UUID(), sa.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('application_id', sa.UUID(), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('scheduled_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scheduled_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('timezone', sa.String(100), nullable=False, server_default='UTC'),
        sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='45'),
        sa.Column('calendar_event_id', sa.String(255), nullable=True),
        sa.Column('meeting_url', sa.String(500), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='SCHEDULED'),
        sa.Column('candidate_email_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('candidate_email_id', sa.String(255), nullable=True),
        sa.Column('invitation_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_interview_schedules_status', 'interview_schedules', ['status'])


def downgrade() -> None:
    op.drop_table('interview_schedules')
