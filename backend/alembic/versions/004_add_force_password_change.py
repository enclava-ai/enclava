"""Add force_password_change to users

Revision ID: 004_add_force_password_change
Revises: fd999a559a35
Create Date: 2025-01-31 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_force_password_change'
down_revision = 'fd999a559a35'
branch_labels = None
depends_on = None


def upgrade():
    # Add force_password_change column to users table
    op.add_column('users', sa.Column('force_password_change', sa.Boolean(), default=False, nullable=False, server_default='false'))


def downgrade():
    # Remove force_password_change column from users table
    op.drop_column('users', 'force_password_change')