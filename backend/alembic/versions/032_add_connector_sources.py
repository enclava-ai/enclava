"""Add connector_sources and connector_sync_jobs tables

Revision ID: 032_add_connector_sources
Revises: 031_add_collection_acl
Create Date: 2026-06-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '032_add_connector_sources'
down_revision = '031_add_collection_acl'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'connector_sources',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('connector_type', sa.String(50), nullable=False, index=True),
        sa.Column(
            'collection_id',
            sa.Integer(),
            sa.ForeignKey('rag_collections.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('encrypted_credentials', sa.Text(), nullable=True),
        sa.Column('sync_frequency', sa.String(20), nullable=False, server_default='PT1H'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_status', sa.String(20), nullable=True),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('last_sync_docs_indexed', sa.Integer(), nullable=True),
        sa.Column('last_sync_docs_failed', sa.Integer(), nullable=True),
        sa.Column('checkpoint', sa.JSON(), nullable=True),
        sa.Column(
            'created_by_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        'connector_sync_jobs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column(
            'connector_id',
            sa.Integer(),
            sa.ForeignKey('connector_sources.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('status', sa.String(20), nullable=False, server_default='idle'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('docs_indexed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('docs_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Also add external_id and last_synced_at to rag_documents for connector dedup
    op.add_column(
        'rag_documents',
        sa.Column(
            'connector_source_id',
            sa.Integer(),
            sa.ForeignKey('connector_sources.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
    )
    op.add_column(
        'rag_documents',
        sa.Column('external_id', sa.String(512), nullable=True, index=True),
    )
    op.add_column(
        'rag_documents',
        sa.Column('external_updated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column('rag_documents', 'external_updated_at')
    op.drop_column('rag_documents', 'external_id')
    op.drop_column('rag_documents', 'connector_source_id')
    op.drop_table('connector_sync_jobs')
    op.drop_table('connector_sources')
