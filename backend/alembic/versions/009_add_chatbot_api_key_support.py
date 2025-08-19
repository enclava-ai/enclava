"""Add chatbot API key support

Revision ID: 009_add_chatbot_api_key_support
Revises: 004_add_api_key_budget_fields
Create Date: 2025-01-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '009_add_chatbot_api_key_support'
down_revision = '004_add_api_key_budget_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Add allowed_chatbots column to api_keys table"""
    # Add the allowed_chatbots column
    op.add_column('api_keys', sa.Column('allowed_chatbots', sa.JSON(), nullable=True))
    
    # Update existing records to have empty allowed_chatbots list
    op.execute("UPDATE api_keys SET allowed_chatbots = '[]' WHERE allowed_chatbots IS NULL")
    
    # Make the column non-nullable with a default
    op.alter_column('api_keys', 'allowed_chatbots', nullable=False, server_default='[]')


def downgrade():
    """Remove allowed_chatbots column from api_keys table"""
    op.drop_column('api_keys', 'allowed_chatbots')