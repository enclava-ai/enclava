"""Consolidated ground truth database schema

This migration represents the complete, accurate database schema based on the actual
model files in the codebase. All legacy migrations have been consolidated into this
single migration to ensure the database matches what the models expect.

Revision ID: 000_consolidated_ground_truth_schema
Revises: 
Create Date: 2025-08-22 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '000_ground_truth'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the complete database schema based on actual model definitions"""
    
    # Create WorkflowStatus enum using raw SQL to avoid SQLAlchemy conflicts
    op.execute("CREATE TYPE workflowstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')")
    
    # Define the enum for use in table definitions
    workflow_status_enum = postgresql.ENUM(
        'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 
        name='workflowstatus',
        create_type=False  # Don't auto-create since we created it above
    )

    # ========================================
    # CORE USER MANAGEMENT
    # ========================================
    
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_verified', sa.Boolean(), nullable=True, default=False),
        sa.Column('role', sa.String(), nullable=True, default="user"),
        sa.Column('permissions', sa.JSON(), nullable=True),
        sa.Column('avatar_url', sa.String(), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('company', sa.String(), nullable=True),
        sa.Column('website', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('preferences', sa.JSON(), nullable=True),
        sa.Column('notification_settings', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # ========================================
    # API KEY MANAGEMENT 
    # ========================================
    
    # Create api_keys table (based on actual model)
    op.create_table('api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('key_hash', sa.String(), nullable=False),
        sa.Column('key_prefix', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('permissions', sa.JSON(), nullable=True),
        sa.Column('scopes', sa.JSON(), nullable=True),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=True, default=60),
        sa.Column('rate_limit_per_hour', sa.Integer(), nullable=True, default=3600),
        sa.Column('rate_limit_per_day', sa.Integer(), nullable=True, default=86400),
        sa.Column('allowed_models', sa.JSON(), nullable=True),
        sa.Column('allowed_endpoints', sa.JSON(), nullable=True),
        sa.Column('allowed_ips', sa.JSON(), nullable=True),
        sa.Column('allowed_chatbots', sa.JSON(), nullable=True),
        sa.Column('is_unlimited', sa.Boolean(), nullable=True, default=True),
        sa.Column('budget_limit_cents', sa.Integer(), nullable=True),
        sa.Column('budget_type', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('total_requests', sa.Integer(), nullable=True, default=0),
        sa.Column('total_tokens', sa.Integer(), nullable=True, default=0),
        sa.Column('total_cost', sa.Integer(), nullable=True, default=0),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_keys_id'), 'api_keys', ['id'], unique=False)
    op.create_index(op.f('ix_api_keys_key_hash'), 'api_keys', ['key_hash'], unique=True)
    op.create_index(op.f('ix_api_keys_key_prefix'), 'api_keys', ['key_prefix'], unique=False)

    # ========================================
    # BUDGET & USAGE TRACKING
    # ========================================
    
    # Create budgets table (based on actual model)
    op.create_table('budgets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('api_key_id', sa.Integer(), nullable=True),
        sa.Column('limit_cents', sa.Integer(), nullable=False),
        sa.Column('warning_threshold_cents', sa.Integer(), nullable=True),
        sa.Column('period_type', sa.String(), nullable=False, default="monthly"),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('current_usage_cents', sa.Integer(), nullable=True, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_exceeded', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_warning_sent', sa.Boolean(), nullable=True, default=False),
        sa.Column('enforce_hard_limit', sa.Boolean(), nullable=True, default=True),
        sa.Column('enforce_warning', sa.Boolean(), nullable=True, default=True),
        sa.Column('allowed_models', sa.JSON(), nullable=True),
        sa.Column('allowed_endpoints', sa.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('currency', sa.String(), nullable=True, default="USD"),
        sa.Column('auto_renew', sa.Boolean(), nullable=True, default=True),
        sa.Column('rollover_unused', sa.Boolean(), nullable=True, default=False),
        sa.Column('notification_settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_reset_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_budgets_id'), 'budgets', ['id'], unique=False)

    # Create usage_tracking table (based on actual model)
    op.create_table('usage_tracking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_key_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('budget_id', sa.Integer(), nullable=True),
        sa.Column('endpoint', sa.String(), nullable=False),
        sa.Column('method', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('request_tokens', sa.Integer(), nullable=True, default=0),
        sa.Column('response_tokens', sa.Integer(), nullable=True, default=0),
        sa.Column('total_tokens', sa.Integer(), nullable=True, default=0),
        sa.Column('cost_cents', sa.Integer(), nullable=True, default=0),
        sa.Column('cost_currency', sa.String(), nullable=True, default="USD"),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('request_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['budget_id'], ['budgets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usage_tracking_id'), 'usage_tracking', ['id'], unique=False)

    # ========================================
    # AUDIT SYSTEM
    # ========================================
    
    # Create audit_logs table (based on actual model)
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('severity', sa.String(), nullable=True, default="low"),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True, default=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('old_values', sa.JSON(), nullable=True),
        sa.Column('new_values', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)

    # ========================================
    # RAG SYSTEM 
    # ========================================
    
    # Create rag_collections table (based on actual model)
    op.create_table('rag_collections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('qdrant_collection_name', sa.String(length=255), nullable=False),
        sa.Column('document_count', sa.Integer(), nullable=False, default=0),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False, default=0),
        sa.Column('vector_count', sa.Integer(), nullable=False, default=0),
        sa.Column('status', sa.String(length=50), nullable=False, default='active'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rag_collections_id'), 'rag_collections', ['id'], unique=False)
    op.create_index(op.f('ix_rag_collections_name'), 'rag_collections', ['name'], unique=False)
    op.create_index(op.f('ix_rag_collections_qdrant_collection_name'), 'rag_collections', ['qdrant_collection_name'], unique=True)

    # Create rag_documents table (based on actual model)
    op.create_table('rag_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('collection_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, default='processing'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('converted_content', sa.Text(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=False, default=0),
        sa.Column('character_count', sa.Integer(), nullable=False, default=0),
        sa.Column('vector_count', sa.Integer(), nullable=False, default=0),
        sa.Column('chunk_size', sa.Integer(), nullable=False, default=1000),
        sa.Column('document_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['collection_id'], ['rag_collections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rag_documents_id'), 'rag_documents', ['id'], unique=False)
    op.create_index(op.f('ix_rag_documents_collection_id'), 'rag_documents', ['collection_id'], unique=False)

    # ========================================
    # CHATBOT SYSTEM (String IDs + JSON config)
    # ========================================
    
    # Create chatbot_instances table (based on actual model - String IDs)
    op.create_table('chatbot_instances',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create chatbot_conversations table (based on actual model - String IDs)
    op.create_table('chatbot_conversations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('chatbot_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('context_data', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['chatbot_id'], ['chatbot_instances.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create chatbot_messages table (based on actual model - String IDs)
    op.create_table('chatbot_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('message_metadata', sa.JSON(), nullable=True),
        sa.Column('sources', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['chatbot_conversations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create chatbot_analytics table (based on actual model)
    op.create_table('chatbot_analytics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chatbot_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('cost_cents', sa.Integer(), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('rag_used', sa.Boolean(), nullable=True, default=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['chatbot_id'], ['chatbot_instances.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # ========================================
    # PROMPT TEMPLATE SYSTEM (String IDs)
    # ========================================
    
    # Create prompt_templates table (based on actual model - String IDs)
    op.create_table('prompt_templates',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type_key', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prompt_templates_id'), 'prompt_templates', ['id'], unique=False)
    op.create_index(op.f('ix_prompt_templates_name'), 'prompt_templates', ['name'], unique=False)
    op.create_index(op.f('ix_prompt_templates_type_key'), 'prompt_templates', ['type_key'], unique=True)

    # Create prompt_variables table (based on actual model - String IDs)
    op.create_table('prompt_variables',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('variable_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('example_value', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prompt_variables_id'), 'prompt_variables', ['id'], unique=False)
    op.create_index(op.f('ix_prompt_variables_variable_name'), 'prompt_variables', ['variable_name'], unique=True)

    # ========================================
    # WORKFLOW SYSTEM (String IDs + Enum)
    # ========================================
    
    # Create workflow_definitions table (based on actual model - String IDs)
    op.create_table('workflow_definitions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=True, default="1.0.0"),
        sa.Column('steps', sa.JSON(), nullable=False),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('timeout', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create workflow_executions table (based on actual model - String IDs + Enum)
    op.create_table('workflow_executions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('status', workflow_status_enum, nullable=True),
        sa.Column('current_step', sa.String(), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('results', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('executed_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflow_definitions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create workflow_step_logs table (based on actual model - String IDs)
    op.create_table('workflow_step_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('execution_id', sa.String(), nullable=False),
        sa.Column('step_id', sa.String(), nullable=False),
        sa.Column('step_name', sa.String(length=255), nullable=False),
        sa.Column('step_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # ========================================
    # MODULE SYSTEM
    # ========================================
    
    # Create modules table (based on actual model)
    op.create_table('modules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('module_type', sa.String(), nullable=True, default="custom"),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('author', sa.String(), nullable=True),
        sa.Column('license', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, default="inactive"),
        sa.Column('is_enabled', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_core', sa.Boolean(), nullable=True, default=False),
        sa.Column('config_schema', sa.JSON(), nullable=True),
        sa.Column('config_values', sa.JSON(), nullable=True),
        sa.Column('default_config', sa.JSON(), nullable=True),
        sa.Column('dependencies', sa.JSON(), nullable=True),
        sa.Column('conflicts', sa.JSON(), nullable=True),
        sa.Column('install_path', sa.String(), nullable=True),
        sa.Column('entry_point', sa.String(), nullable=True),
        sa.Column('interceptor_chains', sa.JSON(), nullable=True),
        sa.Column('execution_order', sa.Integer(), nullable=True, default=100),
        sa.Column('api_endpoints', sa.JSON(), nullable=True),
        sa.Column('required_permissions', sa.JSON(), nullable=True),
        sa.Column('security_level', sa.String(), nullable=True, default="low"),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('module_metadata', sa.JSON(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True, default=0),
        sa.Column('last_started', sa.DateTime(), nullable=True),
        sa.Column('last_stopped', sa.DateTime(), nullable=True),
        sa.Column('request_count', sa.Integer(), nullable=True, default=0),
        sa.Column('success_count', sa.Integer(), nullable=True, default=0),
        sa.Column('error_count_runtime', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('installed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_modules_id'), 'modules', ['id'], unique=False)
    op.create_index(op.f('ix_modules_name'), 'modules', ['name'], unique=True)

    # ========================================
    # PLUGIN SYSTEM (UUID-based, comprehensive)
    # ========================================
    
    # Create plugins table (based on actual model - UUID)
    op.create_table('plugins',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('author', sa.String(length=200), nullable=True),
        sa.Column('homepage', sa.String(length=500), nullable=True),
        sa.Column('repository', sa.String(length=500), nullable=True),
        sa.Column('package_path', sa.String(length=500), nullable=False),
        sa.Column('manifest_hash', sa.String(length=64), nullable=False),
        sa.Column('package_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, default="installed"),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('auto_enable', sa.Boolean(), nullable=False, default=False),
        sa.Column('installed_at', sa.DateTime(), nullable=False),
        sa.Column('enabled_at', sa.DateTime(), nullable=True),
        sa.Column('last_updated_at', sa.DateTime(), nullable=True),
        sa.Column('installed_by_user_id', sa.Integer(), nullable=False),
        sa.Column('manifest_data', sa.JSON(), nullable=True),
        sa.Column('config_schema', sa.JSON(), nullable=True),
        sa.Column('default_config', sa.JSON(), nullable=True),
        sa.Column('required_permissions', sa.JSON(), nullable=True),
        sa.Column('api_scopes', sa.JSON(), nullable=True),
        sa.Column('resource_limits', sa.JSON(), nullable=True),
        sa.Column('database_name', sa.String(length=100), nullable=True),
        sa.Column('database_url', sa.String(length=1000), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True, default=0),
        sa.Column('last_error_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['installed_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_plugin_status_enabled', 'plugins', ['status', 'enabled'], unique=False)
    op.create_index('idx_plugin_user_status', 'plugins', ['installed_by_user_id', 'status'], unique=False)
    op.create_index(op.f('ix_plugins_name'), 'plugins', ['name'], unique=True)
    op.create_index(op.f('ix_plugins_slug'), 'plugins', ['slug'], unique=True)
    op.create_index(op.f('ix_plugins_enabled'), 'plugins', ['enabled'], unique=False)
    op.create_index(op.f('ix_plugins_status'), 'plugins', ['status'], unique=False)
    op.create_unique_constraint(None, 'plugins', ['database_name'])

    # Create plugin_configurations table (based on actual model - UUID)
    op.create_table('plugin_configurations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plugin_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config_data', sa.JSON(), nullable=False),
        sa.Column('encrypted_data', sa.Text(), nullable=True),
        sa.Column('schema_version', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_plugin_config_user_active', 'plugin_configurations', ['plugin_id', 'user_id', 'is_active'], unique=False)

    # Create plugin_instances table (based on actual model - UUID)
    op.create_table('plugin_instances',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plugin_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('configuration_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('instance_name', sa.String(length=200), nullable=False),
        sa.Column('process_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default="starting"),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
        sa.Column('stop_time', sa.DateTime(), nullable=True),
        sa.Column('restart_count', sa.Integer(), nullable=True, default=0),
        sa.Column('memory_usage_mb', sa.Integer(), nullable=True),
        sa.Column('cpu_usage_percent', sa.Integer(), nullable=True),
        sa.Column('health_status', sa.String(length=20), nullable=True, default="unknown"),
        sa.Column('health_message', sa.Text(), nullable=True),
        sa.Column('last_health_check', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True, default=0),
        sa.ForeignKeyConstraint(['configuration_id'], ['plugin_configurations.id'], ),
        sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_plugin_instance_status', 'plugin_instances', ['plugin_id', 'status'], unique=False)
    op.create_index(op.f('ix_plugin_instances_status'), 'plugin_instances', ['status'], unique=False)

    # Create plugin_audit_logs table (based on actual model - UUID)
    op.create_table('plugin_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plugin_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('instance_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource', sa.String(length=200), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('api_key_id', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('request_data', sa.JSON(), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_data', sa.JSON(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
        sa.ForeignKeyConstraint(['instance_id'], ['plugin_instances.id'], ),
        sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_plugin_audit_event_type', 'plugin_audit_logs', ['event_type', 'timestamp'], unique=False)
    op.create_index('idx_plugin_audit_plugin_time', 'plugin_audit_logs', ['plugin_id', 'timestamp'], unique=False)
    op.create_index('idx_plugin_audit_user_time', 'plugin_audit_logs', ['user_id', 'timestamp'], unique=False)
    op.create_index(op.f('ix_plugin_audit_logs_event_type'), 'plugin_audit_logs', ['event_type'], unique=False)
    op.create_index(op.f('ix_plugin_audit_logs_success'), 'plugin_audit_logs', ['success'], unique=False)
    op.create_index(op.f('ix_plugin_audit_logs_timestamp'), 'plugin_audit_logs', ['timestamp'], unique=False)

    # Create plugin_cron_jobs table (based on actual model - UUID)
    op.create_table('plugin_cron_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plugin_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_name', sa.String(length=200), nullable=False),
        sa.Column('job_id', sa.String(length=100), nullable=False),
        sa.Column('schedule', sa.String(length=100), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=True, default="UTC"),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('function_name', sa.String(length=200), nullable=False),
        sa.Column('job_data', sa.JSON(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_duration_ms', sa.Integer(), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=True, default=0),
        sa.Column('success_count', sa.Integer(), nullable=True, default=0),
        sa.Column('error_count', sa.Integer(), nullable=True, default=0),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_at', sa.DateTime(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=True, default=3),
        sa.Column('retry_delay_seconds', sa.Integer(), nullable=True, default=60),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_plugin_cron_next_run', 'plugin_cron_jobs', ['enabled', 'next_run_at'], unique=False)
    op.create_index('idx_plugin_cron_plugin', 'plugin_cron_jobs', ['plugin_id', 'enabled'], unique=False)
    op.create_index(op.f('ix_plugin_cron_jobs_job_id'), 'plugin_cron_jobs', ['job_id'], unique=True)
    op.create_index(op.f('ix_plugin_cron_jobs_enabled'), 'plugin_cron_jobs', ['enabled'], unique=False)
    op.create_index(op.f('ix_plugin_cron_jobs_next_run_at'), 'plugin_cron_jobs', ['next_run_at'], unique=False)

    # Create plugin_api_gateways table (based on actual model - UUID)
    op.create_table('plugin_api_gateways',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plugin_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('base_path', sa.String(length=200), nullable=False),
        sa.Column('internal_url', sa.String(length=500), nullable=False),
        sa.Column('require_authentication', sa.Boolean(), nullable=False, default=True),
        sa.Column('allowed_methods', sa.JSON(), nullable=True),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=True, default=60),
        sa.Column('rate_limit_per_hour', sa.Integer(), nullable=True, default=1000),
        sa.Column('cors_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('cors_origins', sa.JSON(), nullable=True),
        sa.Column('cors_methods', sa.JSON(), nullable=True),
        sa.Column('cors_headers', sa.JSON(), nullable=True),
        sa.Column('circuit_breaker_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('failure_threshold', sa.Integer(), nullable=True, default=5),
        sa.Column('recovery_timeout_seconds', sa.Integer(), nullable=True, default=60),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('last_health_check', sa.DateTime(), nullable=True),
        sa.Column('health_status', sa.String(length=20), nullable=True, default="unknown"),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plugin_api_gateways_enabled'), 'plugin_api_gateways', ['enabled'], unique=False)
    op.create_unique_constraint(None, 'plugin_api_gateways', ['base_path'])
    op.create_unique_constraint(None, 'plugin_api_gateways', ['plugin_id'])

    # Create plugin_permissions table (based on actual model - UUID)
    op.create_table('plugin_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plugin_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('permission_name', sa.String(length=200), nullable=False),
        sa.Column('granted', sa.Boolean(), nullable=False, default=True),
        sa.Column('granted_at', sa.DateTime(), nullable=False),
        sa.Column('granted_by_user_id', sa.Integer(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_by_user_id', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['granted_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id'], ),
        sa.ForeignKeyConstraint(['revoked_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_plugin_permission_active', 'plugin_permissions', ['plugin_id', 'user_id', 'granted'], unique=False)
    op.create_index('idx_plugin_permission_plugin_name', 'plugin_permissions', ['plugin_id', 'permission_name'], unique=False)
    op.create_index('idx_plugin_permission_user_plugin', 'plugin_permissions', ['user_id', 'plugin_id'], unique=False)


def downgrade() -> None:
    """Drop all tables in reverse dependency order"""
    
    # Drop plugin system tables first (most dependent)
    op.drop_table('plugin_permissions')
    op.drop_table('plugin_api_gateways')
    op.drop_table('plugin_cron_jobs')
    op.drop_table('plugin_audit_logs')
    op.drop_table('plugin_instances')
    op.drop_table('plugin_configurations')
    op.drop_table('plugins')
    
    # Drop workflow system
    op.drop_table('workflow_step_logs')
    op.drop_table('workflow_executions')
    op.drop_table('workflow_definitions')
    
    # Drop modules
    op.drop_table('modules')
    
    # Drop prompt system
    op.drop_table('prompt_variables')
    op.drop_table('prompt_templates')
    
    # Drop chatbot system
    op.drop_table('chatbot_analytics')
    op.drop_table('chatbot_messages')
    op.drop_table('chatbot_conversations')
    op.drop_table('chatbot_instances')
    
    # Drop RAG system
    op.drop_table('rag_documents')
    op.drop_table('rag_collections')
    
    # Drop audit system
    op.drop_table('audit_logs')
    
    # Drop usage and budget system
    op.drop_table('usage_tracking')
    op.drop_table('budgets')
    
    # Drop API keys
    op.drop_table('api_keys')
    
    # Drop users (base table)
    op.drop_table('users')
    
    # Drop enums
    op.execute('DROP TYPE workflowstatus')