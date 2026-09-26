"""create interview answer analyses and extend interview questions

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-26 12:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to interview_questions if not present
    op.add_column('interview_questions', sa.Column('plan_question_id', sa.UUID(), nullable=True))
    op.add_column('interview_questions', sa.Column('parent_question_id', sa.UUID(), nullable=True))
    op.add_column('interview_questions', sa.Column('question_type', sa.String(50), nullable=False, server_default='PLANNED'))
    op.add_column('interview_questions', sa.Column('concept', sa.String(100), nullable=True))
    op.create_foreign_key('fk_interview_questions_plan_q', 'interview_questions', 'interview_plan_questions', ['plan_question_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_interview_questions_parent_q', 'interview_questions', 'interview_questions', ['parent_question_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_interview_questions_plan_question_id', 'interview_questions', ['plan_question_id'])

    # Make capability_id nullable on interview_questions
    op.alter_column('interview_questions', 'capability_id', nullable=True)

    # 2. Create interview_answer_analyses table
    op.create_table(
        'interview_answer_analyses',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('session_id', sa.UUID(), sa.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('question_id', sa.UUID(), sa.ForeignKey('interview_questions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('interview_answer_analyses')
    op.drop_constraint('fk_interview_questions_parent_q', 'interview_questions', type_='foreignkey')
    op.drop_constraint('fk_interview_questions_plan_q', 'interview_questions', type_='foreignkey')
    op.drop_index('ix_interview_questions_plan_question_id', table_name='interview_questions')
    op.drop_column('interview_questions', 'concept')
    op.drop_column('interview_questions', 'question_type')
    op.drop_column('interview_questions', 'parent_question_id')
    op.drop_column('interview_questions', 'plan_question_id')
