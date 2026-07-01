"""Remove legacy chatbot storage

Revision ID: 033_remove_chatbots
Revises: 032_add_connector_sources
Create Date: 2026-06-30
"""

from alembic import op


revision = "033_remove_chatbots"
down_revision = "032_add_connector_sources"
branch_labels = None
depends_on = None


def upgrade():
    """Drop chatbot-era tables and columns from existing installations."""
    op.execute("DROP INDEX IF EXISTS idx_usage_records_chatbot_created")
    op.execute("ALTER TABLE usage_records DROP COLUMN IF EXISTS chatbot_id")
    op.execute("ALTER TABLE api_keys DROP COLUMN IF EXISTS allowed_chatbots")

    op.execute("DROP TABLE IF EXISTS chatbot_analytics CASCADE")
    op.execute("DROP TABLE IF EXISTS chatbot_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS chatbot_conversations CASCADE")
    op.execute("DROP TABLE IF EXISTS chatbot_instances CASCADE")


def downgrade():
    """Chatbot storage is intentionally not restored."""
    pass
