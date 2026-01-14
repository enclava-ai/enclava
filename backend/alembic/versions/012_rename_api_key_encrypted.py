"""Rename api_key_encrypted to api_key (remove encryption)

Revision ID: 012_rename_api_key_encrypted
Revises: 011_agent_temperature_to_float
Create Date: 2025-12-17

Removes encryption from MCP server API keys by renaming the column
and clearing existing (encrypted) values since they are no longer usable.
Users will need to re-enter their API keys after this migration.
"""

from alembic import op


# revision identifiers
revision = '012_rename_api_key_encrypted'
down_revision = '011_agent_temperature_to_float'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename api_key_encrypted to api_key and clear existing encrypted values."""
    # Rename the column
    op.alter_column(
        'mcp_servers',
        'api_key_encrypted',
        new_column_name='api_key'
    )

    # Clear existing values since they were encrypted and are no longer usable
    op.execute("UPDATE mcp_servers SET api_key = NULL")


def downgrade() -> None:
    """Rename api_key back to api_key_encrypted."""
    # Clear values first since plaintext keys shouldn't be "encrypted" column
    op.execute("UPDATE mcp_servers SET api_key = NULL")

    op.alter_column(
        'mcp_servers',
        'api_key',
        new_column_name='api_key_encrypted'
    )
