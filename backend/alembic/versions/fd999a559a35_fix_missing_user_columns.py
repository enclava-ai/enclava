"""fix missing user columns

Revision ID: fd999a559a35
Revises: 003_add_notifications_tables
Create Date: 2025-10-30 11:33:42.236622

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fd999a559a35"
down_revision = "003_add_notifications_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing columns to users table
    # These columns should have been added in 001_add_roles_table.py but were not
    
    # Use try/except to handle cases where columns might already exist
    try:
        op.add_column("users", sa.Column("custom_permissions", sa.JSON(), nullable=True, default=dict))
    except Exception:
        pass  # Column might already exist
        
    try:
        op.add_column("users", sa.Column("account_locked", sa.Boolean(), nullable=True, default=False))
    except Exception:
        pass
        
    try:
        op.add_column("users", sa.Column("account_locked_until", sa.DateTime(), nullable=True))
    except Exception:
        pass
        
    try:
        op.add_column("users", sa.Column("failed_login_attempts", sa.Integer(), nullable=True, default=0))
    except Exception:
        pass
        
    try:
        op.add_column("users", sa.Column("last_failed_login", sa.DateTime(), nullable=True))
    except Exception:
        pass


def downgrade() -> None:
    # Remove the columns
    try:
        op.drop_column("users", "last_failed_login")
    except Exception:
        pass
    try:
        op.drop_column("users", "failed_login_attempts")
    except Exception:
        pass
    try:
        op.drop_column("users", "account_locked_until")
    except Exception:
        pass
    try:
        op.drop_column("users", "account_locked")
    except Exception:
        pass
    try:
        op.drop_column("users", "custom_permissions")
    except Exception:
        pass
