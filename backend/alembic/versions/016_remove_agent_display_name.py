"""Remove display_name from agent_configs

Simplify agent creation by using just 'name' instead of separate name and display_name.

Revision ID: 016_remove_display_name
Revises: 015_agent_conversations
Create Date: 2024-12-20
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '016_remove_display_name'
down_revision = '015_agent_conversations'
branch_labels = None
depends_on = None


def upgrade():
    """Remove display_name column from agent_configs."""
    op.drop_column('agent_configs', 'display_name')


def downgrade():
    """Add display_name column back to agent_configs."""
    op.add_column(
        'agent_configs',
        sa.Column('display_name', sa.String(200), nullable=True)
    )

    # Copy name to display_name for existing records
    op.execute("UPDATE agent_configs SET display_name = name WHERE display_name IS NULL")

    # Make it non-nullable after populating
    op.alter_column('agent_configs', 'display_name', nullable=False)
