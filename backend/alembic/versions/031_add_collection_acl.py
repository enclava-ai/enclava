"""Add collection ACL fields (owner, visibility, allowed_role_level)

Revision ID: 031_add_collection_acl
Revises: 030_update_extract_scopes
Create Date: 2026-06-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '031_add_collection_acl'
down_revision = '030_update_extract_scopes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'rag_collections',
        sa.Column(
            'owner_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_rag_collections_owner_user_id',
        'rag_collections',
        ['owner_user_id'],
    )
    op.add_column(
        'rag_collections',
        sa.Column(
            'visibility',
            sa.String(20),
            nullable=False,
            server_default='team',
        ),
    )
    op.add_column(
        'rag_collections',
        sa.Column('allowed_role_level', sa.String(20), nullable=True),
    )


def downgrade():
    op.drop_column('rag_collections', 'allowed_role_level')
    op.drop_column('rag_collections', 'visibility')
    op.drop_index('ix_rag_collections_owner_user_id', table_name='rag_collections')
    op.drop_column('rag_collections', 'owner_user_id')
