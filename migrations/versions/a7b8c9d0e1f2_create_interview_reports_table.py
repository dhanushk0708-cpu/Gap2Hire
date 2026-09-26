"""create interview reports table

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-26 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'interview_reports',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('interview_session_id', sa.UUID(), sa.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        sa.Column('status', sa.String(50), nullable=False, default='GENERATING', index=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('generation_source', sa.String(50), nullable=False, default='SYSTEM_AI'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('strengths', sa.JSON(), nullable=False, default=list),
        sa.Column('demonstrated_capabilities', sa.JSON(), nullable=False, default=list),
        sa.Column('claimed_capabilities', sa.JSON(), nullable=False, default=list),
        sa.Column('unknown_capabilities', sa.JSON(), nullable=False, default=list),
        sa.Column('verification_needed', sa.JSON(), nullable=False, default=list),
        sa.Column('evidence_findings', sa.JSON(), nullable=False, default=list),
        sa.Column('round_summaries', sa.JSON(), nullable=False, default=list),
        sa.Column('question_findings', sa.JSON(), nullable=False, default=list),
        sa.Column('follow_up_findings', sa.JSON(), nullable=False, default=list),
        sa.Column('integrity_summary', sa.JSON(), nullable=False, default=dict),
        sa.Column('unresolved_areas', sa.JSON(), nullable=False, default=list),
        sa.Column('recommendations_for_human_review', sa.JSON(), nullable=False, default=list),
        sa.Column('metadata_json', sa.JSON(), nullable=False, default=dict),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('interview_reports')
