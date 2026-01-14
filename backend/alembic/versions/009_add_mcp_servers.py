"""Add mcp_servers table

Revision ID: 009_add_mcp_servers
Revises: 008_add_agent_configs
Create Date: 2024-12-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_add_mcp_servers'
down_revision = '008_add_agent_configs'
branch_labels = None
depends_on = None


def upgrade():
    """Create mcp_servers table for external MCP server configurations."""
    op.create_table(
        'mcp_servers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        # Connection settings
        sa.Column('server_url', sa.String(500), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        # Access control
        sa.Column('is_global', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        # Cached tool discovery
        sa.Column('cached_tools', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('last_connected_at', sa.DateTime(), nullable=True),
        sa.Column('last_connection_status', sa.String(50), nullable=True),
        sa.Column('last_connection_error', sa.Text(), nullable=True),
        # Usage tracking
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # Add indexes for performance
    op.create_index('ix_mcp_servers_name', 'mcp_servers', ['name'])
    op.create_index('ix_mcp_servers_is_global', 'mcp_servers', ['is_global'])
    op.create_index('ix_mcp_servers_is_active', 'mcp_servers', ['is_active'])
    op.create_index('ix_mcp_servers_created_by_user_id', 'mcp_servers', ['created_by_user_id'])


def downgrade():
    """Drop mcp_servers table."""
    op.drop_index('ix_mcp_servers_created_by_user_id', table_name='mcp_servers')
    op.drop_index('ix_mcp_servers_is_active', table_name='mcp_servers')
    op.drop_index('ix_mcp_servers_is_global', table_name='mcp_servers')
    op.drop_index('ix_mcp_servers_name', table_name='mcp_servers')
    op.drop_table('mcp_servers')
