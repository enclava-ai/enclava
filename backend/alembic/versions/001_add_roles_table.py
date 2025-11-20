"""add roles table

Revision ID: 001
Revises: 000_ground_truth
Create Date: 2025-01-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001_add_roles_table'
down_revision = '000_ground_truth'
branch_labels = None
depends_on = None

def upgrade():
    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('level', sa.String(length=20), nullable=False),
        sa.Column('permissions', sa.JSON(), nullable=True),
        sa.Column('can_manage_users', sa.Boolean(), nullable=True, default=False),
        sa.Column('can_manage_budgets', sa.Boolean(), nullable=True, default=False),
        sa.Column('can_view_reports', sa.Boolean(), nullable=True, default=False),
        sa.Column('can_manage_tools', sa.Boolean(), nullable=True, default=False),
        sa.Column('inherits_from', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_system_role', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for roles
    op.create_index(op.f('ix_roles_id'), 'roles', ['id'], unique=False)
    op.create_index(op.f('ix_roles_name'), 'roles', ['name'], unique=True)
    op.create_index(op.f('ix_roles_level'), 'roles', ['level'], unique=False)

    # Add role_id to users table
    op.add_column('users', sa.Column('role_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_users_role_id', 'users', 'roles',
        ['role_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_users_role_id', 'users', ['role_id'])

def downgrade():
    # Remove role_id from users
    op.drop_index('ix_users_role_id', table_name='users')
    op.drop_constraint('fk_users_role_id', table_name='users', type_='foreignkey')
    op.drop_column('users', 'role_id')

    # Drop roles table
    op.drop_index(op.f('ix_roles_level'), table_name='roles')
    op.drop_index(op.f('ix_roles_name'), table_name='roles')
    op.drop_index(op.f('ix_roles_id'), table_name='roles')
    op.drop_table('roles')