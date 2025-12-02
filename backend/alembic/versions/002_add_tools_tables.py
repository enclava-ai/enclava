"""add tools tables

Revision ID: 002
Revises: 001_add_roles_table
Create Date: 2025-01-30 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '002_add_tools_tables'
down_revision = '001_add_roles_table'
branch_labels = None
depends_on = None

def upgrade():
    # Create tool_categories table
    op.create_table(
        'tool_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tool_categories_id'), 'tool_categories', ['id'], unique=False)
    op.create_index(op.f('ix_tool_categories_name'), 'tool_categories', ['name'], unique=True)

    # Create tools table
    op.create_table(
        'tools',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tool_type', sa.String(length=20), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('parameters_schema', sa.JSON(), nullable=True),
        sa.Column('return_schema', sa.JSON(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=True, default=30),
        sa.Column('max_memory_mb', sa.Integer(), nullable=True, default=256),
        sa.Column('max_cpu_seconds', sa.Float(), nullable=True, default=10.0),
        sa.Column('docker_image', sa.String(length=200), nullable=True),
        sa.Column('docker_command', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_approved', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True, default=0),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tools_id'), 'tools', ['id'], unique=False)
    op.create_index(op.f('ix_tools_name'), 'tools', ['name'], unique=False)
    op.create_foreign_key(
        'fk_tools_created_by_user_id', 'tools', 'users',
        ['created_by_user_id'], ['id'], ondelete='CASCADE'
    )

    # Create tool_executions table
    op.create_table(
        'tool_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tool_id', sa.Integer(), nullable=False),
        sa.Column('executed_by_user_id', sa.Integer(), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('output', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('return_code', sa.Integer(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('memory_used_mb', sa.Float(), nullable=True),
        sa.Column('cpu_time_ms', sa.Integer(), nullable=True),
        sa.Column('container_id', sa.String(length=100), nullable=True),
        sa.Column('docker_logs', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tool_executions_id'), 'tool_executions', ['id'], unique=False)
    op.create_foreign_key(
        'fk_tool_executions_tool_id', 'tool_executions', 'tools',
        ['tool_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_tool_executions_executed_by_user_id', 'tool_executions', 'users',
        ['executed_by_user_id'], ['id'], ondelete='CASCADE'
    )

def downgrade():
    # Drop tool_executions table
    op.drop_constraint('fk_tool_executions_executed_by_user_id', table_name='tool_executions', type_='foreignkey')
    op.drop_constraint('fk_tool_executions_tool_id', table_name='tool_executions', type_='foreignkey')
    op.drop_index(op.f('ix_tool_executions_id'), table_name='tool_executions')
    op.drop_table('tool_executions')

    # Drop tools table
    op.drop_constraint('fk_tools_created_by_user_id', table_name='tools', type_='foreignkey')
    op.drop_index(op.f('ix_tools_name'), table_name='tools')
    op.drop_index(op.f('ix_tools_id'), table_name='tools')
    op.drop_table('tools')

    # Drop tool_categories table
    op.drop_index(op.f('ix_tool_categories_name'), table_name='tool_categories')
    op.drop_index(op.f('ix_tool_categories_id'), table_name='tool_categories')
    op.drop_table('tool_categories')