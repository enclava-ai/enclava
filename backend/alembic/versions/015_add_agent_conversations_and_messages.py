"""Add agent_conversations and agent_messages tables

Revision ID: 015_agent_conversations
Revises: 014_add_allowed_agents
Create Date: 2025-01-20

Creates dedicated tables for agent conversations and messages, replacing
the hack of using chatbot tables for agent chats.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '015_agent_conversations'
down_revision = '014_add_allowed_agents'
branch_labels = None
depends_on = None


def upgrade():
    # Create agent_conversations table
    op.create_table(
        'agent_conversations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_config_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('context_data', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['agent_config_id'], ['agent_configs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for agent_conversations table
    op.create_index('idx_agent_conversations_id', 'agent_conversations', ['id'])
    op.create_index('idx_agent_conversations_agent_config_id', 'agent_conversations', ['agent_config_id'])
    op.create_index('idx_agent_conversations_user_id', 'agent_conversations', ['user_id'])
    op.create_index('idx_agent_conversations_created_at', 'agent_conversations', ['created_at'])
    op.create_index('idx_agent_conversations_updated_at', 'agent_conversations', ['updated_at'])

    # Create agent_messages table
    op.create_table(
        'agent_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('conversation_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('tool_calls', sa.JSON(), nullable=True),
        sa.Column('tool_call_id', sa.String(length=100), nullable=True),
        sa.Column('tool_name', sa.String(length=100), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('message_metadata', sa.JSON(), nullable=True),
        sa.Column('sources', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['agent_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for agent_messages table
    op.create_index('idx_agent_messages_id', 'agent_messages', ['id'])
    op.create_index('idx_agent_messages_conversation_id', 'agent_messages', ['conversation_id'])
    op.create_index('idx_agent_messages_timestamp', 'agent_messages', ['timestamp'])
    op.create_index('idx_agent_messages_role', 'agent_messages', ['role'])


def downgrade():
    # Drop agent_messages table and its indexes
    op.drop_index('idx_agent_messages_role', table_name='agent_messages')
    op.drop_index('idx_agent_messages_timestamp', table_name='agent_messages')
    op.drop_index('idx_agent_messages_conversation_id', table_name='agent_messages')
    op.drop_index('idx_agent_messages_id', table_name='agent_messages')
    op.drop_table('agent_messages')

    # Drop agent_conversations table and its indexes
    op.drop_index('idx_agent_conversations_updated_at', table_name='agent_conversations')
    op.drop_index('idx_agent_conversations_created_at', table_name='agent_conversations')
    op.drop_index('idx_agent_conversations_user_id', table_name='agent_conversations')
    op.drop_index('idx_agent_conversations_agent_config_id', table_name='agent_conversations')
    op.drop_index('idx_agent_conversations_id', table_name='agent_conversations')
    op.drop_table('agent_conversations')
