"""Change agent_configs temperature from Integer to Float

Revision ID: 011_agent_temperature_to_float
Revises: 010_add_mcp_api_key_header_name
Create Date: 2024-12-17

Temperature was stored as int * 10 (e.g., 0.7 -> 7) but this caused
float precision issues. Now storing as actual float value (0.0 to 1.0).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011_agent_temperature_to_float'
down_revision = '010_add_mcp_api_key_header_name'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add a temporary column with Float type
    op.add_column('agent_configs', sa.Column('temperature_new', sa.Float(), nullable=True))

    # Step 2: Copy and convert data (divide by 10 to get actual temperature)
    op.execute('UPDATE agent_configs SET temperature_new = temperature / 10.0')

    # Step 3: Drop the old column
    op.drop_column('agent_configs', 'temperature')

    # Step 4: Rename new column to temperature
    op.alter_column('agent_configs', 'temperature_new', new_column_name='temperature')

    # Step 5: Set NOT NULL and default
    op.alter_column('agent_configs', 'temperature',
                    existing_type=sa.Float(),
                    nullable=False,
                    server_default='0.7')


def downgrade() -> None:
    # Step 1: Add temporary Integer column
    op.add_column('agent_configs', sa.Column('temperature_old', sa.Integer(), nullable=True))

    # Step 2: Copy and convert data (multiply by 10)
    op.execute('UPDATE agent_configs SET temperature_old = CAST(temperature * 10 AS INTEGER)')

    # Step 3: Drop the Float column
    op.drop_column('agent_configs', 'temperature')

    # Step 4: Rename old column back
    op.alter_column('agent_configs', 'temperature_old', new_column_name='temperature')

    # Step 5: Set NOT NULL and default
    op.alter_column('agent_configs', 'temperature',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='7')
