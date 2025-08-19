"""Add budget fields to API keys

Revision ID: 004_add_api_key_budget_fields
Revises: 8bf097417ff0
Create Date: 2024-07-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_api_key_budget_fields'
down_revision = '8bf097417ff0'
branch_labels = None
depends_on = None


def upgrade():
    """Add budget-related fields to api_keys table"""
    # Add budget configuration columns
    op.add_column('api_keys', sa.Column('is_unlimited', sa.Boolean(), default=True, nullable=False))
    op.add_column('api_keys', sa.Column('budget_limit_cents', sa.Integer(), nullable=True))
    op.add_column('api_keys', sa.Column('budget_type', sa.String(), nullable=True))
    
    # Set default values for existing records
    op.execute("UPDATE api_keys SET is_unlimited = true WHERE is_unlimited IS NULL")


def downgrade():
    """Remove budget-related fields from api_keys table"""
    op.drop_column('api_keys', 'budget_type')
    op.drop_column('api_keys', 'budget_limit_cents')
    op.drop_column('api_keys', 'is_unlimited')