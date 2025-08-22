"""Initial Zammad plugin schema

Revision ID: 001
Revises: 
Create Date: 2024-12-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial Zammad plugin schema"""
    
    # Create zammad_configurations table
    op.create_table(
        'zammad_configurations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('zammad_url', sa.String(500), nullable=False),
        sa.Column('api_token_encrypted', sa.Text(), nullable=False),
        sa.Column('chatbot_id', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column('ai_summarization_enabled', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column('auto_summarize', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column('sync_enabled', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column('sync_interval_hours', sa.Integer(), nullable=False, server_default=sa.text('2')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create zammad_tickets table
    op.create_table(
        'zammad_tickets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('zammad_ticket_id', sa.String(50), nullable=False),
        sa.Column('configuration_id', UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('priority', sa.String(50), nullable=True),
        sa.Column('customer_id', sa.String(50), nullable=True),
        sa.Column('group_id', sa.String(50), nullable=True),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('last_synced', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['configuration_id'], ['zammad_configurations.id'], ondelete='CASCADE'),
    )
    
    # Create indexes for performance
    op.create_index('idx_zammad_configurations_user_id', 'zammad_configurations', ['user_id'])
    op.create_index('idx_zammad_configurations_user_active', 'zammad_configurations', ['user_id', 'is_active'])
    
    op.create_index('idx_zammad_tickets_zammad_id', 'zammad_tickets', ['zammad_ticket_id'])
    op.create_index('idx_zammad_tickets_config_id', 'zammad_tickets', ['configuration_id'])
    op.create_index('idx_zammad_tickets_status', 'zammad_tickets', ['status'])
    op.create_index('idx_zammad_tickets_last_synced', 'zammad_tickets', ['last_synced'])
    
    # Create updated_at trigger function if it doesn't exist
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE 'plpgsql';
    """)
    
    # Create triggers to automatically update updated_at columns
    op.execute("""
        CREATE TRIGGER update_zammad_configurations_updated_at
        BEFORE UPDATE ON zammad_configurations
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_zammad_tickets_updated_at
        BEFORE UPDATE ON zammad_tickets
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Drop Zammad plugin schema"""
    
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS update_zammad_tickets_updated_at ON zammad_tickets;")
    op.execute("DROP TRIGGER IF EXISTS update_zammad_configurations_updated_at ON zammad_configurations;")
    
    # Drop indexes
    op.drop_index('idx_zammad_tickets_last_synced')
    op.drop_index('idx_zammad_tickets_status')
    op.drop_index('idx_zammad_tickets_config_id')
    op.drop_index('idx_zammad_tickets_zammad_id')
    op.drop_index('idx_zammad_configurations_user_active')
    op.drop_index('idx_zammad_configurations_user_id')
    
    # Drop tables (tickets first due to foreign key)
    op.drop_table('zammad_tickets')
    op.drop_table('zammad_configurations')
    
    # Note: We don't drop the update_updated_at_column function as it might be used by other tables