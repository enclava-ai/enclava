"""add_zammad_integration_tables

Revision ID: 9645f764a517
Revises: 010_add_workflow_tables_only
Create Date: 2025-08-19 19:55:18.895986

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '9645f764a517'
down_revision = '010_add_workflow_tables_only'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create zammad_tickets table
    op.create_table(
        'zammad_tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zammad_ticket_id', sa.Integer(), nullable=False),
        sa.Column('ticket_number', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('priority', sa.String(), nullable=True),
        sa.Column('customer_email', sa.String(), nullable=True),
        sa.Column('processing_status', sa.String(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('chatbot_id', sa.String(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('context_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('zammad_created_at', sa.DateTime(), nullable=True),
        sa.Column('zammad_updated_at', sa.DateTime(), nullable=True),
        sa.Column('zammad_article_count', sa.Integer(), nullable=False),
        sa.Column('config_snapshot', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['processed_by_user_id'], ['users.id'], ),
    )
    
    # Create indexes for zammad_tickets
    op.create_index('idx_zammad_tickets_status_created', 'zammad_tickets', ['processing_status', 'created_at'])
    op.create_index('idx_zammad_tickets_state_processed', 'zammad_tickets', ['state', 'processed_at'])
    op.create_index('idx_zammad_tickets_user_status', 'zammad_tickets', ['processed_by_user_id', 'processing_status'])
    op.create_index(op.f('ix_zammad_tickets_id'), 'zammad_tickets', ['id'])
    op.create_index(op.f('ix_zammad_tickets_ticket_number'), 'zammad_tickets', ['ticket_number'])
    op.create_index(op.f('ix_zammad_tickets_zammad_ticket_id'), 'zammad_tickets', ['zammad_ticket_id'], unique=True)

    # Create zammad_processing_logs table
    op.create_table(
        'zammad_processing_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.String(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('initiated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('config_used', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('filters_applied', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('tickets_found', sa.Integer(), nullable=False),
        sa.Column('tickets_processed', sa.Integer(), nullable=False),
        sa.Column('tickets_failed', sa.Integer(), nullable=False),
        sa.Column('tickets_skipped', sa.Integer(), nullable=False),
        sa.Column('processing_time_seconds', sa.Integer(), nullable=True),
        sa.Column('average_time_per_ticket', sa.Integer(), nullable=True),
        sa.Column('errors_encountered', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['initiated_by_user_id'], ['users.id'], ),
    )
    
    # Create indexes for zammad_processing_logs
    op.create_index('idx_processing_logs_batch_status', 'zammad_processing_logs', ['batch_id', 'status'])
    op.create_index('idx_processing_logs_user_started', 'zammad_processing_logs', ['initiated_by_user_id', 'started_at'])
    op.create_index(op.f('ix_zammad_processing_logs_batch_id'), 'zammad_processing_logs', ['batch_id'])
    op.create_index(op.f('ix_zammad_processing_logs_id'), 'zammad_processing_logs', ['id'])

    # Create zammad_configurations table
    op.create_table(
        'zammad_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('zammad_url', sa.String(), nullable=False),
        sa.Column('api_token_encrypted', sa.String(), nullable=False),
        sa.Column('chatbot_id', sa.String(), nullable=False),
        sa.Column('process_state', sa.String(), nullable=False),
        sa.Column('max_tickets', sa.Integer(), nullable=False),
        sa.Column('skip_existing', sa.Boolean(), nullable=False),
        sa.Column('auto_process', sa.Boolean(), nullable=False),
        sa.Column('process_interval', sa.Integer(), nullable=False),
        sa.Column('summary_template', sa.Text(), nullable=True),
        sa.Column('custom_settings', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    
    # Create indexes for zammad_configurations
    op.create_index('idx_zammad_config_user_active', 'zammad_configurations', ['user_id', 'is_active'])
    op.create_index('idx_zammad_config_user_default', 'zammad_configurations', ['user_id', 'is_default'])
    op.create_index(op.f('ix_zammad_configurations_id'), 'zammad_configurations', ['id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('zammad_configurations')
    op.drop_table('zammad_processing_logs')
    op.drop_table('zammad_tickets')