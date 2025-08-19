"""Add prompt templates for editable chatbot prompts

Revision ID: 005_add_prompt_templates
Revises: 004_add_api_key_budget_fields
Create Date: 2025-08-07 17:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime
import uuid

# revision identifiers, used by Alembic.
revision = '005_add_prompt_templates'
down_revision = '004_add_api_key_budget_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create prompt_templates table
    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('type_key', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('is_default', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # Create prompt_variables table
    op.create_table(
        'prompt_variables',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('variable_name', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('example_value', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # Insert default prompt templates
    prompt_templates_table = sa.table(
        'prompt_templates',
        sa.column('id', sa.String),
        sa.column('name', sa.String),
        sa.column('type_key', sa.String),
        sa.column('description', sa.Text),
        sa.column('system_prompt', sa.Text),
        sa.column('is_default', sa.Boolean),
        sa.column('is_active', sa.Boolean),
        sa.column('version', sa.Integer),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime)
    )

    current_time = datetime.utcnow()
    
    default_prompts = [
        {
            'id': str(uuid.uuid4()),
            'name': 'General Assistant',
            'type_key': 'assistant',
            'description': 'Helpful AI assistant for general questions and tasks',
            'system_prompt': 'You are a helpful AI assistant. Provide accurate, concise, and friendly responses. Always aim to be helpful while being honest about your limitations. When you don\'t know something, say so clearly. Be professional but approachable in your communication style.',
            'is_default': True,
            'is_active': True,
            'version': 1,
            'created_at': current_time,
            'updated_at': current_time
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Customer Support',
            'type_key': 'customer_support',
            'description': 'Professional customer service chatbot',
            'system_prompt': 'You are a professional customer support representative. Be empathetic, professional, and solution-focused in all interactions. Always try to understand the customer\'s issue fully before providing solutions. Use the knowledge base to provide accurate information. When you cannot resolve an issue, explain clearly how the customer can escalate or get further help. Maintain a helpful and patient tone even in difficult situations.',
            'is_default': True,
            'is_active': True,
            'version': 1,
            'created_at': current_time,
            'updated_at': current_time
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Educational Tutor',
            'type_key': 'teacher',
            'description': 'Educational tutor and learning assistant',
            'system_prompt': 'You are an experienced educational tutor and learning facilitator. Break down complex concepts into understandable, digestible parts. Use analogies, examples, and step-by-step explanations to help students learn. Encourage critical thinking through thoughtful questions. Be patient, supportive, and encouraging. Adapt your teaching style to different learning preferences. When a student makes mistakes, guide them to the correct answer rather than just providing it.',
            'is_default': True,
            'is_active': True,
            'version': 1,
            'created_at': current_time,
            'updated_at': current_time
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Research Assistant',
            'type_key': 'researcher',
            'description': 'Research assistant with fact-checking focus',
            'system_prompt': 'You are a thorough research assistant with a focus on accuracy and evidence-based information. Provide well-researched, factual information with sources when possible. Be thorough in your analysis and present multiple perspectives when relevant topics have different viewpoints. Always distinguish between established facts, current research, and opinions. When information is uncertain or contested, clearly communicate the level of confidence and supporting evidence.',
            'is_default': True,
            'is_active': True,
            'version': 1,
            'created_at': current_time,
            'updated_at': current_time
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Creative Writing Assistant',
            'type_key': 'creative_writer',
            'description': 'Creative writing and storytelling assistant',
            'system_prompt': 'You are an experienced creative writing mentor and storytelling expert. Help with brainstorming ideas, character development, plot structure, dialogue, and creative expression. Be imaginative and inspiring while providing constructive, actionable feedback. Encourage experimentation with different writing styles and techniques. When reviewing work, balance praise for strengths with specific suggestions for improvement. Help writers find their unique voice while mastering fundamental storytelling principles.',
            'is_default': True,
            'is_active': True,
            'version': 1,
            'created_at': current_time,
            'updated_at': current_time
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Custom Chatbot',
            'type_key': 'custom',
            'description': 'Fully customizable chatbot with user-defined personality',
            'system_prompt': 'You are a helpful AI assistant. Your personality, expertise, and behavior will be defined by the user through custom instructions. Follow the user\'s guidance on how to respond, what tone to use, and what role to play. Be adaptable and responsive to the specific needs and preferences outlined in your configuration.',
            'is_default': True,
            'is_active': True,
            'version': 1,
            'created_at': current_time,
            'updated_at': current_time
        }
    ]

    op.bulk_insert(prompt_templates_table, default_prompts)

    # Insert default prompt variables
    variables_table = sa.table(
        'prompt_variables',
        sa.column('id', sa.String),
        sa.column('variable_name', sa.String),
        sa.column('description', sa.Text),
        sa.column('example_value', sa.String),
        sa.column('is_active', sa.Boolean),
        sa.column('created_at', sa.DateTime)
    )

    default_variables = [
        {
            'id': str(uuid.uuid4()),
            'variable_name': '{user_name}',
            'description': 'The name of the user chatting with the bot',
            'example_value': 'John Smith',
            'is_active': True,
            'created_at': current_time
        },
        {
            'id': str(uuid.uuid4()),
            'variable_name': '{context}',
            'description': 'Additional context from RAG or previous conversation',
            'example_value': 'Based on the uploaded documents...',
            'is_active': True,
            'created_at': current_time
        },
        {
            'id': str(uuid.uuid4()),
            'variable_name': '{company_name}',
            'description': 'Your company or organization name',
            'example_value': 'Acme Corporation',
            'is_active': True,
            'created_at': current_time
        },
        {
            'id': str(uuid.uuid4()),
            'variable_name': '{current_date}',
            'description': 'Current date and time',
            'example_value': '2025-08-07 17:50:00',
            'is_active': True,
            'created_at': current_time
        }
    ]

    op.bulk_insert(variables_table, default_variables)


def downgrade() -> None:
    op.drop_table('prompt_variables')
    op.drop_table('prompt_templates')