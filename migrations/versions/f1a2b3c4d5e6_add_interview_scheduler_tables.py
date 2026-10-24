"""add interview scheduler extensions notifications and booking slots

Revision ID: f1a2b3c4d5e6
Revises: a3f8c9d1e2b4
Create Date: 2026-10-24 11:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'a3f8c9d1e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend interview_schedules table
    op.add_column('interview_schedules', sa.Column('interviewer_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    op.add_column('interview_schedules', sa.Column('interview_type', sa.String(50), nullable=False, server_default='ONLINE'))
    op.add_column('interview_schedules', sa.Column('interview_reference', sa.String(100), nullable=True))
    op.add_column('interview_schedules', sa.Column('location', sa.String(255), nullable=True))
    op.add_column('interview_schedules', sa.Column('cancellation_reason', sa.Text(), nullable=True))
    op.add_column('interview_schedules', sa.Column('booking_token', sa.String(100), nullable=True))

    op.alter_column('interview_schedules', 'meeting_url', existing_type=sa.String(500), nullable=True)

    op.create_index('ix_interview_schedules_interviewer_id', 'interview_schedules', ['interviewer_id'])
    op.create_index('ix_interview_schedules_interview_reference', 'interview_schedules', ['interview_reference'], unique=True)
    op.create_index('ix_interview_schedules_booking_token', 'interview_schedules', ['booking_token'])

    # 2. Create simulated_notifications table
    op.create_table(
        'simulated_notifications',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('interview_schedule_id', sa.UUID(), sa.ForeignKey('interview_schedules.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('recipient', sa.String(255), nullable=False, index=True),
        sa.Column('recipient_name', sa.String(255), nullable=True),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('interview_reference', sa.String(100), nullable=False, index=True),
        sa.Column('notification_type', sa.String(50), nullable=False, index=True),
        sa.Column('delivery_mode', sa.String(50), nullable=False, server_default='DEMO_SIMULATED'),
        sa.Column('delivery_status', sa.String(50), nullable=False, server_default='DELIVERED'),
        sa.Column('demo_banner', sa.String(255), nullable=False, server_default='DEMO MODE — EMAILS NOT SENT'),
        sa.Column('idempotency_key', sa.String(255), nullable=True, unique=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 3. Create interview_booking_slots table
    op.create_table(
        'interview_booking_slots',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('application_id', sa.UUID(), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('interviewer_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='45'),
        sa.Column('interview_type', sa.String(50), nullable=False, server_default='ONLINE'),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('booking_token', sa.String(100), nullable=False, index=True),
        sa.Column('is_booked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('booked_schedule_id', sa.UUID(), sa.ForeignKey('interview_schedules.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_interview_booking_slots_start_time', 'interview_booking_slots', ['start_time'])
    op.create_index('ix_interview_booking_slots_is_booked', 'interview_booking_slots', ['is_booked'])


def downgrade() -> None:
    op.drop_table('interview_booking_slots')
    op.drop_table('simulated_notifications')
    op.drop_index('ix_interview_schedules_booking_token', table_name='interview_schedules')
    op.drop_index('ix_interview_schedules_interview_reference', table_name='interview_schedules')
    op.drop_index('ix_interview_schedules_interviewer_id', table_name='interview_schedules')
    op.drop_column('interview_schedules', 'booking_token')
    op.drop_column('interview_schedules', 'cancellation_reason')
    op.drop_column('interview_schedules', 'location')
    op.drop_column('interview_schedules', 'interview_reference')
    op.drop_column('interview_schedules', 'interview_type')
    op.drop_column('interview_schedules', 'interviewer_id')
    op.alter_column('interview_schedules', 'meeting_url', existing_type=sa.String(500), nullable=False)
