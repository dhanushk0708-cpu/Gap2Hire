"""create post hire outcomes table

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-26 15:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'post_hire_outcomes',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('application_id', sa.UUID(), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('job_id', sa.UUID(), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('recorded_by', sa.UUID(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('outcome_period', sa.String(50), nullable=False, default='90_DAYS'),
        sa.Column('capability_id', sa.UUID(), sa.ForeignKey('capabilities.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('capability_name', sa.String(255), nullable=False),
        sa.Column('expected_capability_description', sa.Text(), nullable=True),
        sa.Column('observed_outcome_description', sa.Text(), nullable=False),
        sa.Column('outcome_status', sa.String(50), nullable=False, index=True),
        sa.Column('manager_notes', sa.Text(), nullable=True),
        sa.Column('evidence_reference', sa.String(512), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=False, default=dict),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('post_hire_outcomes')
