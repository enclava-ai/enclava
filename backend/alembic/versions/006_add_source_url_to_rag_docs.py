"""Add source_url to rag_documents

Revision ID: 006_add_source_url_to_rag_docs
Revises: 005_fix_user_nullable_columns
Create Date: 2025-11-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "006_add_source_url_to_rag_docs"
down_revision = "005_fix_user_nullable_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add source_url column to rag_documents table.
    This column will store the original URL for web-scraped documents.
    """
    op.add_column(
        "rag_documents",
        sa.Column("source_url", sa.String(500), nullable=True)
    )


def downgrade() -> None:
    """
    Remove source_url column from rag_documents table.
    """
    op.drop_column("rag_documents", "source_url")
