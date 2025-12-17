"""Add tool support to chatbot messages

Revision ID: 007_add_chatbot_tool_support
Revises: 006_add_source_url_to_rag_docs
Create Date: 2024-12-16 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_add_chatbot_tool_support'
down_revision = '006_add_source_url_to_rag_docs'
branch_labels = None
depends_on = None


def upgrade():
    """Add tool-related columns to chatbot_messages table.

    Changes:
    1. Make content column nullable (tool-call messages may have no text content)
    2. Add tool_calls column for assistant messages with tool calls
    3. Add tool_call_id column for tool response messages
    4. Add tool_name column to track which tool was called
    """
    # Make content nullable (required for tool-call messages with no text)
    op.alter_column('chatbot_messages', 'content',
                    existing_type=sa.Text(),
                    nullable=True)

    # Add tool-related columns
    op.add_column('chatbot_messages', sa.Column('tool_calls', sa.JSON(), nullable=True))
    op.add_column('chatbot_messages', sa.Column('tool_call_id', sa.String(100), nullable=True))
    op.add_column('chatbot_messages', sa.Column('tool_name', sa.String(100), nullable=True))


def downgrade():
    """Remove tool support from chatbot_messages table."""
    # Drop tool columns
    op.drop_column('chatbot_messages', 'tool_name')
    op.drop_column('chatbot_messages', 'tool_call_id')
    op.drop_column('chatbot_messages', 'tool_calls')

    # Restore NOT NULL constraint on content
    # WARNING: This may fail if NULL values exist in the content column
    op.alter_column('chatbot_messages', 'content',
                    existing_type=sa.Text(),
                    nullable=False)
