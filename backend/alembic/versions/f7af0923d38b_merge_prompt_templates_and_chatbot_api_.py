"""merge prompt templates and chatbot api key support

Revision ID: f7af0923d38b
Revises: 005_add_prompt_templates, 009_add_chatbot_api_key_support
Create Date: 2025-08-18 06:51:17.515233

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7af0923d38b'
down_revision = ('005_add_prompt_templates', '009_add_chatbot_api_key_support')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass