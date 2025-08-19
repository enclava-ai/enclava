"""Fix budget and usage_tracking columns

Revision ID: 003
Revises: 002
Create Date: 2025-07-24 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing columns to budgets table
    op.add_column('budgets', sa.Column('api_key_id', sa.Integer(), nullable=True))
    op.add_column('budgets', sa.Column('limit_cents', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('budgets', sa.Column('warning_threshold_cents', sa.Integer(), nullable=True))
    op.add_column('budgets', sa.Column('period_type', sa.String(), nullable=False, server_default='monthly'))
    op.add_column('budgets', sa.Column('current_usage_cents', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('budgets', sa.Column('is_exceeded', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('budgets', sa.Column('is_warning_sent', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('budgets', sa.Column('enforce_hard_limit', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('budgets', sa.Column('enforce_warning', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('budgets', sa.Column('auto_renew', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('budgets', sa.Column('rollover_unused', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('budgets', sa.Column('notification_settings', sa.JSON(), nullable=True))
    
    # Create foreign key for api_key_id
    op.create_foreign_key('fk_budgets_api_key_id', 'budgets', 'api_keys', ['api_key_id'], ['id'])
    
    # Update usage_tracking table
    op.add_column('usage_tracking', sa.Column('budget_id', sa.Integer(), nullable=True))
    op.add_column('usage_tracking', sa.Column('model', sa.String(), nullable=True))
    op.add_column('usage_tracking', sa.Column('request_tokens', sa.Integer(), nullable=True))
    op.add_column('usage_tracking', sa.Column('response_tokens', sa.Integer(), nullable=True))
    op.add_column('usage_tracking', sa.Column('cost_cents', sa.Integer(), nullable=True))
    op.add_column('usage_tracking', sa.Column('cost_currency', sa.String(), nullable=True, server_default='USD'))
    op.add_column('usage_tracking', sa.Column('response_time_ms', sa.Integer(), nullable=True))
    op.add_column('usage_tracking', sa.Column('request_metadata', sa.JSON(), nullable=True))
    
    # Create foreign key for budget_id
    op.create_foreign_key('fk_usage_tracking_budget_id', 'usage_tracking', 'budgets', ['budget_id'], ['id'])
    
    # Update modules table
    op.add_column('modules', sa.Column('module_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove added columns from modules
    op.drop_column('modules', 'module_metadata')
    
    # Remove added columns and constraints from usage_tracking
    op.drop_constraint('fk_usage_tracking_budget_id', 'usage_tracking', type_='foreignkey')
    op.drop_column('usage_tracking', 'request_metadata')
    op.drop_column('usage_tracking', 'response_time_ms')
    op.drop_column('usage_tracking', 'cost_currency')
    op.drop_column('usage_tracking', 'cost_cents')
    op.drop_column('usage_tracking', 'response_tokens')
    op.drop_column('usage_tracking', 'request_tokens')
    op.drop_column('usage_tracking', 'model')
    op.drop_column('usage_tracking', 'budget_id')
    
    # Remove added columns and constraints from budgets
    op.drop_constraint('fk_budgets_api_key_id', 'budgets', type_='foreignkey')
    op.drop_column('budgets', 'notification_settings')
    op.drop_column('budgets', 'rollover_unused')
    op.drop_column('budgets', 'auto_renew')
    op.drop_column('budgets', 'enforce_warning')
    op.drop_column('budgets', 'enforce_hard_limit')
    op.drop_column('budgets', 'is_warning_sent')
    op.drop_column('budgets', 'is_exceeded')
    op.drop_column('budgets', 'current_usage_cents')
    op.drop_column('budgets', 'period_type')
    op.drop_column('budgets', 'warning_threshold_cents')
    op.drop_column('budgets', 'limit_cents')
    op.drop_column('budgets', 'api_key_id')