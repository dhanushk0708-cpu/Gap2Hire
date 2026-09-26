"""create candidate hiring decisions table

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-26 15:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'candidate_hiring_decisions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('application_id', sa.UUID(), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('job_id', sa.UUID(), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('decision', sa.String(50), nullable=False, index=True),
        sa.Column('decision_reason', sa.Text(), nullable=False),
        sa.Column('decided_by', sa.UUID(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('report_id', sa.UUID(), sa.ForeignKey('interview_reports.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('previous_decision_id', sa.UUID(), sa.ForeignKey('candidate_hiring_decisions.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('metadata_json', sa.JSON(), nullable=False, default=dict),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('candidate_hiring_decisions')
