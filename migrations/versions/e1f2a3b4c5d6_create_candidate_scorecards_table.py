"""create candidate scorecards table

Revision ID: e1f2a3b4c5d6
Revises: c9d0e1f2a3b4
Create Date: 2026-10-17 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'candidate_scorecards',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('application_id', sa.UUID(), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('job_id', sa.UUID(), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('scorecard_type', sa.String(50), nullable=False, index=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('is_baseline', sa.Boolean(), nullable=False, default=False, index=True),
        sa.Column('interview_session_id', sa.UUID(), sa.ForeignKey('interview_sessions.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('scorecard_data', sa.JSON(), nullable=False, default=dict),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('application_id', 'scorecard_type', 'version', name='uq_candidate_scorecard_app_type_version'),
    )


def downgrade() -> None:
    op.drop_table('candidate_scorecards')
