"""add notifications tables

Revision ID: 003_add_notifications_tables
Revises: 002_add_tools_tables
Create Date: 2025-01-30 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '003_add_notifications_tables'
down_revision = '002_add_tools_tables'
branch_labels = None
depends_on = None

def upgrade():
    # Create notification_templates table
    op.create_table(
        'notification_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notification_type', sa.String(length=20), nullable=False),
        sa.Column('subject_template', sa.Text(), nullable=True),
        sa.Column('body_template', sa.Text(), nullable=False),
        sa.Column('html_template', sa.Text(), nullable=True),
        sa.Column('default_priority', sa.String(length=20), nullable=True, default='normal'),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_templates_id'), 'notification_templates', ['id'], unique=False)
    op.create_index(op.f('ix_notification_templates_name'), 'notification_templates', ['name'], unique=True)

    # Create notification_channels table
    op.create_table(
        'notification_channels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('notification_type', sa.String(length=20), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('credentials', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_default', sa.Boolean(), nullable=True, default=False),
        sa.Column('rate_limit', sa.Integer(), nullable=True, default=100),
        sa.Column('retry_count', sa.Integer(), nullable=True, default=3),
        sa.Column('retry_delay_minutes', sa.Integer(), nullable=True, default=5),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('success_count', sa.Integer(), nullable=True, default=0),
        sa.Column('failure_count', sa.Integer(), nullable=True, default=0),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_channels_id'), 'notification_channels', ['id'], unique=False)
    op.create_index(op.f('ix_notification_channels_name'), 'notification_channels', ['name'], unique=False)

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('html_body', sa.Text(), nullable=True),
        sa.Column('recipients', sa.JSON(), nullable=False),
        sa.Column('cc_recipients', sa.JSON(), nullable=True),
        sa.Column('bcc_recipients', sa.JSON(), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=True, default='normal'),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=True, default=0),
        sa.Column('max_attempts', sa.Integer(), nullable=True, default=3),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('external_id', sa.String(length=200), nullable=True),
        sa.Column('callback_url', sa.String(length=500), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)
    op.create_index(op.f('ix_notifications_status'), 'notifications', ['status'], unique=False)
    op.create_index(op.f('ix_notifications_scheduled_at'), 'notifications', ['scheduled_at'], unique=False)

    # Add foreign key constraints
    op.create_foreign_key(
        'fk_notifications_template_id', 'notifications', 'notification_templates',
        ['template_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_notifications_channel_id', 'notifications', 'notification_channels',
        ['channel_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_notifications_user_id', 'notifications', 'users',
        ['user_id'], ['id'], ondelete='SET NULL'
    )

def downgrade():
    # Drop notifications table
    op.drop_constraint('fk_notifications_user_id', table_name='notifications', type_='foreignkey')
    op.drop_constraint('fk_notifications_channel_id', table_name='notifications', type_='foreignkey')
    op.drop_constraint('fk_notifications_template_id', table_name='notifications', type_='foreignkey')
    op.drop_index(op.f('ix_notifications_scheduled_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_status'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_id'), table_name='notifications')
    op.drop_table('notifications')

    # Drop notification_channels table
    op.drop_index(op.f('ix_notification_channels_name'), table_name='notification_channels')
    op.drop_index(op.f('ix_notification_channels_id'), table_name='notification_channels')
    op.drop_table('notification_channels')

    # Drop notification_templates table
    op.drop_index(op.f('ix_notification_templates_name'), table_name='notification_templates')
    op.drop_index(op.f('ix_notification_templates_id'), table_name='notification_templates')
    op.drop_table('notification_templates')