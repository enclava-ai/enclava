"""Add agent_configs table

Revision ID: 008_add_agent_configs
Revises: 007_add_chatbot_tool_support
Create Date: 2024-12-16 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_add_agent_configs'
down_revision = '007_add_chatbot_tool_support'
branch_labels = None
depends_on = None


def upgrade():
    """Create agent_configs table for pre-configured agents."""
    op.create_table(
        'agent_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('model', sa.String(100), nullable=False, server_default='gpt-oss-120b'),
        sa.Column('temperature', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='2000'),
        sa.Column('tools_config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_template', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    )

    # Add indexes for performance
    op.create_index('ix_agent_configs_name', 'agent_configs', ['name'])
    op.create_index('ix_agent_configs_category', 'agent_configs', ['category'])


def downgrade():
    """Drop agent_configs table."""
    op.drop_index('ix_agent_configs_category', table_name='agent_configs')
    op.drop_index('ix_agent_configs_name', table_name='agent_configs')
    op.drop_table('agent_configs')
