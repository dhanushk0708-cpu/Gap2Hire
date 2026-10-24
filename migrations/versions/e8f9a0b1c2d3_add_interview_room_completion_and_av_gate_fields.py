"""Add interview room completion, duration enforcement, and AV gate fields

Revision ID: e8f9a0b1c2d3
Revises: e7f8a9b0c1d2
Create Date: 2026-10-24 16:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e8f9a0b1c2d3'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add fields to interview_sessions
    op.add_column(
        'interview_sessions',
        sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='30')
    )
    op.add_column(
        'interview_sessions',
        sa.Column('deadline_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'interview_sessions',
        sa.Column('completion_reason', sa.String(length=100), nullable=True)
    )
    op.add_column(
        'interview_sessions',
        sa.Column('report_status', sa.String(length=50), nullable=False, server_default='NOT_STARTED')
    )

    # 2. Add fields to interview_reports
    op.add_column(
        'interview_reports',
        sa.Column('completion_reason', sa.String(length=100), nullable=True)
    )
    op.add_column(
        'interview_reports',
        sa.Column('configured_duration_minutes', sa.Integer(), nullable=True)
    )
    op.add_column(
        'interview_reports',
        sa.Column('transcript', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]')
    )
    op.add_column(
        'interview_reports',
        sa.Column('unanswered_questions', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]')
    )
    op.add_column(
        'interview_reports',
        sa.Column('media_events', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]')
    )
    op.add_column(
        'interview_reports',
        sa.Column('scorecard_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        'interview_reports',
        sa.Column('failure_reason', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('interview_reports', 'failure_reason')
    op.drop_column('interview_reports', 'scorecard_data')
    op.drop_column('interview_reports', 'media_events')
    op.drop_column('interview_reports', 'unanswered_questions')
    op.drop_column('interview_reports', 'transcript')
    op.drop_column('interview_reports', 'configured_duration_minutes')
    op.drop_column('interview_reports', 'completion_reason')

    op.drop_column('interview_sessions', 'report_status')
    op.drop_column('interview_sessions', 'completion_reason')
    op.drop_column('interview_sessions', 'deadline_at')
    op.drop_column('interview_sessions', 'duration_minutes')
