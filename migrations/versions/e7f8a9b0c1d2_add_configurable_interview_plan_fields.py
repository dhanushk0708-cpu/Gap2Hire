"""Add configurable interview plan fields and schedule links

Revision ID: e7f8a9b0c1d2
Revises: f1a2b3c4d5e6
Create Date: 2026-10-24 11:58:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e7f8a9b0c1d2'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add fields to interview_plans
    op.add_column(
        'interview_plans',
        sa.Column('lock_version', sa.Integer(), nullable=False, server_default='1')
    )

    # 2. Add fields to interview_plan_rounds
    op.add_column(
        'interview_plan_rounds',
        sa.Column('difficulty', sa.String(length=50), nullable=False, server_default='MEDIUM')
    )
    op.add_column(
        'interview_plan_rounds',
        sa.Column('description', sa.Text(), nullable=True)
    )
    op.add_column(
        'interview_plan_rounds',
        sa.Column('evaluation_criteria', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        'interview_plan_rounds',
        sa.Column('expected_evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        'interview_plan_rounds',
        sa.Column('question_generation_mode', sa.String(length=50), nullable=False, server_default='AI_GENERATED')
    )

    # 3. Add fields to interview_plan_questions
    op.add_column(
        'interview_plan_questions',
        sa.Column('is_hr_authored', sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        'interview_plan_questions',
        sa.Column('status', sa.String(length=50), nullable=False, server_default='APPROVED')
    )

    # 4. Add plan_id and round_id to interview_schedules
    op.add_column(
        'interview_schedules',
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_interview_schedules_plan_id',
        'interview_schedules',
        'interview_plans',
        ['plan_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index(
        op.f('ix_interview_schedules_plan_id'),
        'interview_schedules',
        ['plan_id'],
        unique=False
    )

    op.add_column(
        'interview_schedules',
        sa.Column('round_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_interview_schedules_round_id',
        'interview_schedules',
        'interview_plan_rounds',
        ['round_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index(
        op.f('ix_interview_schedules_round_id'),
        'interview_schedules',
        ['round_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_interview_schedules_round_id'), table_name='interview_schedules')
    op.drop_constraint('fk_interview_schedules_round_id', 'interview_schedules', type_='foreignkey')
    op.drop_column('interview_schedules', 'round_id')

    op.drop_index(op.f('ix_interview_schedules_plan_id'), table_name='interview_schedules')
    op.drop_constraint('fk_interview_schedules_plan_id', 'interview_schedules', type_='foreignkey')
    op.drop_column('interview_schedules', 'plan_id')

    op.drop_column('interview_plan_questions', 'status')
    op.drop_column('interview_plan_questions', 'is_hr_authored')

    op.drop_column('interview_plan_rounds', 'question_generation_mode')
    op.drop_column('interview_plan_rounds', 'expected_evidence')
    op.drop_column('interview_plan_rounds', 'evaluation_criteria')
    op.drop_column('interview_plan_rounds', 'description')
    op.drop_column('interview_plan_rounds', 'difficulty')

    op.drop_column('interview_plans', 'lock_version')
