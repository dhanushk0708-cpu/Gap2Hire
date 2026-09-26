"""create_interview_dataset_and_plan_tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-26 01:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. interview_dataset_files
    op.create_table(
        'interview_dataset_files',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('job_id', sa.UUID(), sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('total_questions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # 2. interview_question_datasets
    op.create_table(
        'interview_question_datasets',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('file_id', sa.UUID(), sa.ForeignKey('interview_dataset_files.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('concept', sa.String(100), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('question_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 3. interview_dataset_questions
    op.create_table(
        'interview_dataset_questions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('dataset_id', sa.UUID(), sa.ForeignKey('interview_question_datasets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('concept', sa.String(100), nullable=False, index=True),
        sa.Column('difficulty', sa.String(50), nullable=False, server_default='MEDIUM'),
        sa.Column('question_type', sa.String(50), nullable=False, server_default='CONCEPTUAL'),
        sa.Column('expected_topics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata_', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 4. interview_plans
    op.create_table(
        'interview_plans',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('application_id', sa.UUID(), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('job_id', sa.UUID(), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('dataset_file_id', sa.UUID(), sa.ForeignKey('interview_dataset_files.id', ondelete='SET NULL'), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(50), nullable=False, server_default='DRAFT', index=True),
        sa.Column('candidate_strengths_summary', sa.Text(), nullable=True),
        sa.Column('verification_targets_summary', sa.Text(), nullable=True),
        sa.Column('hr_feedback', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_by', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # 5. interview_plan_rounds
    op.create_table(
        'interview_plan_rounds',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('plan_id', sa.UUID(), sa.ForeignKey('interview_plans.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('round_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('objective', sa.Text(), nullable=False),
        sa.Column('concepts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 6. interview_plan_questions
    op.create_table(
        'interview_plan_questions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('round_id', sa.UUID(), sa.ForeignKey('interview_plan_rounds.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('dataset_question_id', sa.UUID(), sa.ForeignKey('interview_dataset_questions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('concept', sa.String(100), nullable=False),
        sa.Column('difficulty', sa.String(50), nullable=False, server_default='MEDIUM'),
        sa.Column('question_type', sa.String(50), nullable=False, server_default='CONCEPTUAL'),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('evidence_being_verified', sa.Text(), nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('interview_plan_questions')
    op.drop_table('interview_plan_rounds')
    op.drop_table('interview_plans')
    op.drop_table('interview_dataset_questions')
    op.drop_table('interview_question_datasets')
    op.drop_table('interview_dataset_files')
