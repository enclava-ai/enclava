"""Add RAG collections and documents tables

Revision ID: 002
Revises: 001
Create Date: 2025-07-23 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create rag_collections table
    op.create_table('rag_collections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('qdrant_collection_name', sa.String(255), nullable=False),
        sa.Column('document_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('vector_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rag_collections_id'), 'rag_collections', ['id'], unique=False)
    op.create_index(op.f('ix_rag_collections_name'), 'rag_collections', ['name'], unique=False)
    op.create_index(op.f('ix_rag_collections_qdrant_collection_name'), 'rag_collections', ['qdrant_collection_name'], unique=True)
    
    # Create rag_documents table
    op.create_table('rag_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('collection_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='processing'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('converted_content', sa.Text(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('character_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('vector_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('chunk_size', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('document_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['collection_id'], ['rag_collections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rag_documents_id'), 'rag_documents', ['id'], unique=False)
    op.create_index(op.f('ix_rag_documents_collection_id'), 'rag_documents', ['collection_id'], unique=False)
    op.create_index(op.f('ix_rag_documents_filename'), 'rag_documents', ['filename'], unique=False)
    op.create_index(op.f('ix_rag_documents_status'), 'rag_documents', ['status'], unique=False)
    op.create_index(op.f('ix_rag_documents_created_at'), 'rag_documents', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_rag_documents_created_at'), table_name='rag_documents')
    op.drop_index(op.f('ix_rag_documents_status'), table_name='rag_documents')
    op.drop_index(op.f('ix_rag_documents_filename'), table_name='rag_documents')
    op.drop_index(op.f('ix_rag_documents_collection_id'), table_name='rag_documents')
    op.drop_index(op.f('ix_rag_documents_id'), table_name='rag_documents')
    op.drop_table('rag_documents')
    
    op.drop_index(op.f('ix_rag_collections_qdrant_collection_name'), table_name='rag_collections')
    op.drop_index(op.f('ix_rag_collections_name'), table_name='rag_collections')
    op.drop_index(op.f('ix_rag_collections_id'), table_name='rag_collections')
    op.drop_table('rag_collections')