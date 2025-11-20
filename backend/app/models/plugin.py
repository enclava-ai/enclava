"""
Plugin System Database Models
Defines the database schema for the isolated plugin architecture
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.database import Base


class Plugin(Base):
    """Plugin registry - tracks all installed plugins"""

    __tablename__ = "plugins"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(
        String(100), unique=True, nullable=False, index=True
    )  # URL-safe identifier

    # Metadata
    display_name = Column(String(200), nullable=False)
    description = Column(Text)
    version = Column(String(50), nullable=False)
    author = Column(String(200))
    homepage = Column(String(500))
    repository = Column(String(500))

    # Plugin file information
    package_path = Column(String(500), nullable=False)  # Path to plugin package
    manifest_hash = Column(String(64), nullable=False)  # SHA256 of manifest file
    package_hash = Column(String(64), nullable=False)  # SHA256 of plugin package

    # Status and lifecycle
    status = Column(String(20), nullable=False, default="installed", index=True)
    # Statuses: installing, installed, enabled, disabled, error, uninstalling
    enabled = Column(Boolean, default=False, nullable=False, index=True)
    auto_enable = Column(Boolean, default=False, nullable=False)

    # Installation tracking
    installed_at = Column(DateTime, nullable=False, default=func.now())
    enabled_at = Column(DateTime)
    last_updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    installed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Configuration and requirements
    manifest_data = Column(JSON)  # Complete plugin.yaml content
    config_schema = Column(JSON)  # JSON schema for plugin configuration
    default_config = Column(JSON)  # Default configuration values

    # Security and permissions
    required_permissions = Column(JSON)  # List of required permission scopes
    api_scopes = Column(JSON)  # Required API access scopes
    resource_limits = Column(JSON)  # Memory, CPU, storage limits

    # Database isolation
    database_name = Column(String(100), unique=True)  # Isolated database name
    database_url = Column(String(1000))  # Connection string for plugin database

    # Error tracking
    last_error = Column(Text)
    error_count = Column(Integer, default=0)
    last_error_at = Column(DateTime)

    # Relationships
    installed_by_user = relationship("User", back_populates="installed_plugins")
    configurations = relationship(
        "PluginConfiguration", back_populates="plugin", cascade="all, delete-orphan"
    )
    instances = relationship(
        "PluginInstance", back_populates="plugin", cascade="all, delete-orphan"
    )
    audit_logs = relationship(
        "PluginAuditLog", back_populates="plugin", cascade="all, delete-orphan"
    )
    cron_jobs = relationship(
        "PluginCronJob", back_populates="plugin", cascade="all, delete-orphan"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_plugin_status_enabled", "status", "enabled"),
        Index("idx_plugin_user_status", "installed_by_user_id", "status"),
    )


class PluginConfiguration(Base):
    """Plugin configuration instances - per user/environment configs"""

    __tablename__ = "plugin_configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_id = Column(UUID(as_uuid=True), ForeignKey("plugins.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Configuration data
    name = Column(String(200), nullable=False)  # Human-readable config name
    description = Column(Text)
    config_data = Column(JSON, nullable=False)  # Non-sensitive configuration values
    encrypted_data = Column(Text)  # Encrypted sensitive fields (JSON string)
    schema_version = Column(String(50))  # Schema version for migration support
    is_active = Column(Boolean, default=False, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    plugin = relationship("Plugin", back_populates="configurations")
    user = relationship("User", foreign_keys=[user_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])

    # Constraints
    __table_args__ = (
        Index("idx_plugin_config_user_active", "plugin_id", "user_id", "is_active"),
    )


class PluginInstance(Base):
    """Plugin runtime instances - tracks running plugin processes"""

    __tablename__ = "plugin_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_id = Column(UUID(as_uuid=True), ForeignKey("plugins.id"), nullable=False)
    configuration_id = Column(
        UUID(as_uuid=True), ForeignKey("plugin_configurations.id")
    )

    # Runtime information
    instance_name = Column(String(200), nullable=False)
    process_id = Column(String(100))  # Docker container ID or process ID
    status = Column(String(20), nullable=False, default="starting", index=True)
    # Statuses: starting, running, stopping, stopped, error, crashed

    # Performance tracking
    start_time = Column(DateTime, nullable=False, default=func.now())
    last_heartbeat = Column(DateTime, default=func.now())
    stop_time = Column(DateTime)
    restart_count = Column(Integer, default=0)

    # Resource usage
    memory_usage_mb = Column(Integer)
    cpu_usage_percent = Column(Integer)

    # Health monitoring
    health_status = Column(String(20), default="unknown")  # healthy, warning, critical
    health_message = Column(Text)
    last_health_check = Column(DateTime)

    # Error tracking
    last_error = Column(Text)
    error_count = Column(Integer, default=0)

    # Relationships
    plugin = relationship("Plugin", back_populates="instances")
    configuration = relationship("PluginConfiguration")

    __table_args__ = (Index("idx_plugin_instance_status", "plugin_id", "status"),)


class PluginAuditLog(Base):
    """Audit logging for all plugin activities"""

    __tablename__ = "plugin_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_id = Column(UUID(as_uuid=True), ForeignKey("plugins.id"), nullable=False)
    instance_id = Column(UUID(as_uuid=True), ForeignKey("plugin_instances.id"))

    # Event details
    event_type = Column(
        String(50), nullable=False, index=True
    )  # api_call, config_change, error, etc.
    action = Column(String(100), nullable=False)
    resource = Column(String(200))  # Resource being accessed

    # Context information
    user_id = Column(Integer, ForeignKey("users.id"))
    api_key_id = Column(Integer, ForeignKey("api_keys.id"))
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(String(500))

    # Request/response data
    request_data = Column(JSON)  # Sanitized request data
    response_status = Column(Integer)
    response_data = Column(JSON)  # Sanitized response data

    # Performance metrics
    duration_ms = Column(Integer)

    # Status and errors
    success = Column(Boolean, nullable=False, index=True)
    error_message = Column(Text)

    # Timestamps
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)

    # Relationships
    plugin = relationship("Plugin", back_populates="audit_logs")
    instance = relationship("PluginInstance")
    user = relationship("User")
    api_key = relationship("APIKey")

    __table_args__ = (
        Index("idx_plugin_audit_plugin_time", "plugin_id", "timestamp"),
        Index("idx_plugin_audit_user_time", "user_id", "timestamp"),
        Index("idx_plugin_audit_event_type", "event_type", "timestamp"),
    )


class PluginCronJob(Base):
    """Plugin scheduled jobs and cron tasks"""

    __tablename__ = "plugin_cron_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_id = Column(UUID(as_uuid=True), ForeignKey("plugins.id"), nullable=False)

    # Job identification
    job_name = Column(String(200), nullable=False)
    job_id = Column(
        String(100), nullable=False, unique=True, index=True
    )  # Unique scheduler ID

    # Schedule configuration
    schedule = Column(String(100), nullable=False)  # Cron expression
    timezone = Column(String(50), default="UTC")
    enabled = Column(Boolean, default=True, nullable=False, index=True)

    # Job details
    description = Column(Text)
    function_name = Column(String(200), nullable=False)  # Plugin function to call
    job_data = Column(JSON)  # Parameters for the job function

    # Execution tracking
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime, index=True)
    last_duration_ms = Column(Integer)
    run_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)

    # Error handling
    last_error = Column(Text)
    last_error_at = Column(DateTime)
    max_retries = Column(Integer, default=3)
    retry_delay_seconds = Column(Integer, default=60)

    # Lifecycle
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    plugin = relationship("Plugin", back_populates="cron_jobs")
    created_by_user = relationship("User")

    __table_args__ = (
        Index("idx_plugin_cron_next_run", "enabled", "next_run_at"),
        Index("idx_plugin_cron_plugin", "plugin_id", "enabled"),
    )


class PluginAPIGateway(Base):
    """API gateway configuration for plugin routing"""

    __tablename__ = "plugin_api_gateways"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_id = Column(
        UUID(as_uuid=True), ForeignKey("plugins.id"), nullable=False, unique=True
    )

    # API routing configuration
    base_path = Column(
        String(200), nullable=False, unique=True
    )  # /api/v1/plugins/zammad
    internal_url = Column(String(500), nullable=False)  # http://plugin-zammad:8000

    # Security settings
    require_authentication = Column(Boolean, default=True, nullable=False)
    allowed_methods = Column(
        JSON, default=["GET", "POST", "PUT", "DELETE"]
    )  # HTTP methods
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_hour = Column(Integer, default=1000)

    # CORS settings
    cors_enabled = Column(Boolean, default=True, nullable=False)
    cors_origins = Column(JSON, default=["*"])
    cors_methods = Column(JSON, default=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    cors_headers = Column(JSON, default=["*"])

    # Circuit breaker settings
    circuit_breaker_enabled = Column(Boolean, default=True, nullable=False)
    failure_threshold = Column(Integer, default=5)
    recovery_timeout_seconds = Column(Integer, default=60)

    # Monitoring
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    last_health_check = Column(DateTime)
    health_status = Column(String(20), default="unknown")  # healthy, unhealthy, timeout

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    plugin = relationship("Plugin")


# Add relationships to existing User model (import this in user.py)
"""
Add to User model:
    installed_plugins = relationship("Plugin", back_populates="installed_by_user")
"""

# Add relationships to existing APIKey model (import this in api_key.py)
"""
Add to APIKey model:
    plugin_audit_logs = relationship("PluginAuditLog", back_populates="api_key")
"""


class PluginPermission(Base):
    """Plugin permission grants - tracks user permissions for plugins"""

    __tablename__ = "plugin_permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_id = Column(UUID(as_uuid=True), ForeignKey("plugins.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Permission details
    permission_name = Column(
        String(200), nullable=False
    )  # e.g., 'chatbot:invoke', 'rag:query'
    granted = Column(
        Boolean, default=True, nullable=False
    )  # True=granted, False=revoked

    # Grant/revoke tracking
    granted_at = Column(DateTime, nullable=False, default=func.now())
    granted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    revoked_at = Column(DateTime)
    revoked_by_user_id = Column(Integer, ForeignKey("users.id"))

    # Metadata
    reason = Column(Text)  # Reason for grant/revocation
    expires_at = Column(DateTime)  # Optional expiration time

    # Relationships
    plugin = relationship("Plugin")
    user = relationship("User", foreign_keys=[user_id])
    granted_by_user = relationship("User", foreign_keys=[granted_by_user_id])
    revoked_by_user = relationship("User", foreign_keys=[revoked_by_user_id])

    __table_args__ = (
        Index("idx_plugin_permission_user_plugin", "user_id", "plugin_id"),
        Index("idx_plugin_permission_plugin_name", "plugin_id", "permission_name"),
        Index("idx_plugin_permission_active", "plugin_id", "user_id", "granted"),
    )
