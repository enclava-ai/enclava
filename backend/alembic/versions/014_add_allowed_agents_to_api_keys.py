"""Add allowed_agents column to api_keys table

Revision ID: 014_add_allowed_agents
Revises: 013_add_responses_conversations
Create Date: 2024-12-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '014_add_allowed_agents'
down_revision = '013_add_responses_conversations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add allowed_agents column to api_keys table
    op.add_column(
        'api_keys',
        sa.Column('allowed_agents', sa.JSON(), nullable=True, server_default='[]')
    )

    # Update existing rows to have empty list
    op.execute("UPDATE api_keys SET allowed_agents = '[]' WHERE allowed_agents IS NULL")


def downgrade() -> None:
    # Remove allowed_agents column
    op.drop_column('api_keys', 'allowed_agents')
