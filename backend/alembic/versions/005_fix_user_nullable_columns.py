"""fix user nullable columns

Revision ID: 005_fix_user_nullable_columns
Revises: 004_add_force_password_change
Create Date: 2025-11-20 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "005_fix_user_nullable_columns"
down_revision = "004_add_force_password_change"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Fix nullable columns in users table:
    - Backfill NULL values for account_locked and failed_login_attempts
    - Set proper server defaults
    - Alter columns to NOT NULL
    """
    # Use connection to execute raw SQL for backfilling
    conn = op.get_bind()

    # Backfill NULL values for account_locked
    conn.execute(
        sa.text("UPDATE users SET account_locked = FALSE WHERE account_locked IS NULL")
    )

    # Backfill NULL values for failed_login_attempts
    conn.execute(
        sa.text("UPDATE users SET failed_login_attempts = 0 WHERE failed_login_attempts IS NULL")
    )

    # Backfill NULL values for custom_permissions (use empty JSON object)
    conn.execute(
        sa.text("UPDATE users SET custom_permissions = '{}' WHERE custom_permissions IS NULL")
    )

    # Now alter columns to NOT NULL with server defaults
    # Note: PostgreSQL syntax
    op.alter_column('users', 'account_locked',
                    existing_type=sa.Boolean(),
                    nullable=False,
                    server_default=sa.false())

    op.alter_column('users', 'failed_login_attempts',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='0')

    op.alter_column('users', 'custom_permissions',
                    existing_type=sa.JSON(),
                    nullable=False,
                    server_default='{}')


def downgrade() -> None:
    """
    Revert columns to nullable (original state from fd999a559a35)
    """
    op.alter_column('users', 'account_locked',
                    existing_type=sa.Boolean(),
                    nullable=True,
                    server_default=None)

    op.alter_column('users', 'failed_login_attempts',
                    existing_type=sa.Integer(),
                    nullable=True,
                    server_default=None)

    op.alter_column('users', 'custom_permissions',
                    existing_type=sa.JSON(),
                    nullable=True,
                    server_default=None)
