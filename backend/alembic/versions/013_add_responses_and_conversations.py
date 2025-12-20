"""Add responses and conversations tables, and tool_resources to agent_configs

Revision ID: 013_add_responses_conversations
Revises: 012_rename_api_key_encrypted
Create Date: 2025-01-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '013_add_responses_conversations'
down_revision = '012_rename_api_key_encrypted'  # Previous migration in chain
branch_labels = None
depends_on = None


def upgrade():
    # Create responses table
    op.create_table(
        'responses',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('object', sa.String(length=20), nullable=False, server_default='response'),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('api_key_id', sa.Integer(), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('input_items', sa.JSON(), nullable=False),
        sa.Column('output_items', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='completed'),
        sa.Column('error', sa.JSON(), nullable=True),
        sa.Column('previous_response_id', sa.String(length=50), nullable=True),
        sa.Column('conversation_id', sa.String(length=50), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('store', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('response_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for responses table
    op.create_index('idx_responses_id', 'responses', ['id'])
    op.create_index('idx_responses_status', 'responses', ['status'])
    op.create_index('idx_responses_created_at', 'responses', ['created_at'])

    # Conditional indexes (PostgreSQL-specific)
    op.create_index(
        'idx_responses_user_id',
        'responses',
        ['user_id'],
        postgresql_where=sa.text('user_id IS NOT NULL')
    )
    op.create_index(
        'idx_responses_api_key_id',
        'responses',
        ['api_key_id'],
        postgresql_where=sa.text('api_key_id IS NOT NULL')
    )
    op.create_index(
        'idx_responses_conversation_id',
        'responses',
        ['conversation_id'],
        postgresql_where=sa.text('conversation_id IS NOT NULL')
    )
    op.create_index(
        'idx_responses_previous_response_id',
        'responses',
        ['previous_response_id'],
        postgresql_where=sa.text('previous_response_id IS NOT NULL')
    )
    op.create_index(
        'idx_responses_expires_at',
        'responses',
        ['expires_at'],
        postgresql_where=sa.text('expires_at IS NOT NULL AND archived_at IS NULL')
    )
    op.create_index(
        'idx_responses_archived_at',
        'responses',
        ['archived_at'],
        postgresql_where=sa.text('archived_at IS NOT NULL')
    )

    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('object', sa.String(length=20), nullable=False, server_default='conversation'),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('api_key_id', sa.Integer(), nullable=True),
        sa.Column('items', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('conversation_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for conversations table
    op.create_index('idx_conversations_id', 'conversations', ['id'])
    op.create_index('idx_conversations_created_at', 'conversations', ['created_at'])
    op.create_index('idx_conversations_updated_at', 'conversations', ['updated_at'])

    op.create_index(
        'idx_conversations_user_id',
        'conversations',
        ['user_id'],
        postgresql_where=sa.text('user_id IS NOT NULL')
    )
    op.create_index(
        'idx_conversations_api_key_id',
        'conversations',
        ['api_key_id'],
        postgresql_where=sa.text('api_key_id IS NOT NULL')
    )

    # Add tool_resources column to agent_configs table
    op.add_column(
        'agent_configs',
        sa.Column('tool_resources', sa.JSON(), nullable=True)
    )


def downgrade():
    # Drop tool_resources column from agent_configs
    op.drop_column('agent_configs', 'tool_resources')
    # Drop conversations table and its indexes
    op.drop_index('idx_conversations_api_key_id', table_name='conversations')
    op.drop_index('idx_conversations_user_id', table_name='conversations')
    op.drop_index('idx_conversations_updated_at', table_name='conversations')
    op.drop_index('idx_conversations_created_at', table_name='conversations')
    op.drop_index('idx_conversations_id', table_name='conversations')
    op.drop_table('conversations')

    # Drop responses table and its indexes
    op.drop_index('idx_responses_archived_at', table_name='responses')
    op.drop_index('idx_responses_expires_at', table_name='responses')
    op.drop_index('idx_responses_previous_response_id', table_name='responses')
    op.drop_index('idx_responses_conversation_id', table_name='responses')
    op.drop_index('idx_responses_api_key_id', table_name='responses')
    op.drop_index('idx_responses_user_id', table_name='responses')
    op.drop_index('idx_responses_created_at', table_name='responses')
    op.drop_index('idx_responses_status', table_name='responses')
    op.drop_index('idx_responses_id', table_name='responses')
    op.drop_table('responses')
