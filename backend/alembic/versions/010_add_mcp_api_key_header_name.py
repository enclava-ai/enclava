"""Add api_key_header_name column to mcp_servers

Revision ID: 010_add_mcp_api_key_header_name
Revises: 009_add_mcp_servers
Create Date: 2025-01-01

Adds api_key_header_name column to allow customizing the HTTP header name
used for API key authentication with different MCP servers.

Common header names:
- Authorization (default, format: "Bearer <key>")
- X-API-Key
- Api-Key
- X-Auth-Token
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '010_add_mcp_api_key_header_name'
down_revision = '009_add_mcp_servers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add api_key_header_name column with default 'Authorization'."""
    op.add_column(
        'mcp_servers',
        sa.Column(
            'api_key_header_name',
            sa.String(100),
            nullable=False,
            server_default='Authorization'
        )
    )


def downgrade() -> None:
    """Remove api_key_header_name column."""
    op.drop_column('mcp_servers', 'api_key_header_name')
