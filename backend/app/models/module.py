"""
Module model for tracking installed modules and their configurations
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text
from app.db.database import Base
from enum import Enum


class ModuleStatus(str, Enum):
    """Module status types"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    LOADING = "loading"
    DISABLED = "disabled"


class ModuleType(str, Enum):
    """Module type categories"""

    CORE = "core"
    INTERCEPTOR = "interceptor"
    ANALYTICS = "analytics"
    SECURITY = "security"
    STORAGE = "storage"
    INTEGRATION = "integration"
    CUSTOM = "custom"


class Module(Base):
    """Module model for tracking installed modules and their configurations"""

    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Module classification
    module_type = Column(String, default=ModuleType.CUSTOM)
    category = Column(String, nullable=True)  # cache, rag, analytics, etc.

    # Module details
    version = Column(String, nullable=False)
    author = Column(String, nullable=True)
    license = Column(String, nullable=True)

    # Module status
    status = Column(String, default=ModuleStatus.INACTIVE)
    is_enabled = Column(Boolean, default=False)
    is_core = Column(Boolean, default=False)  # Core modules cannot be disabled

    # Configuration
    config_schema = Column(JSON, default=dict)  # JSON schema for configuration
    config_values = Column(JSON, default=dict)  # Current configuration values
    default_config = Column(JSON, default=dict)  # Default configuration

    # Dependencies
    dependencies = Column(JSON, default=list)  # List of module dependencies
    conflicts = Column(JSON, default=list)  # List of conflicting modules

    # Installation details
    install_path = Column(String, nullable=True)
    entry_point = Column(String, nullable=True)  # Main module entry point

    # Interceptor configuration
    interceptor_chains = Column(
        JSON, default=list
    )  # Which chains this module hooks into
    execution_order = Column(Integer, default=100)  # Order in interceptor chain

    # API endpoints
    api_endpoints = Column(
        JSON, default=list
    )  # List of API endpoints this module provides

    # Permissions and security
    required_permissions = Column(
        JSON, default=list
    )  # Permissions required to use this module
    security_level = Column(String, default="low")  # low, medium, high, critical

    # Metadata
    tags = Column(JSON, default=list)
    module_metadata = Column(JSON, default=dict)

    # Runtime information
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)
    last_started = Column(DateTime, nullable=True)
    last_stopped = Column(DateTime, nullable=True)

    # Statistics
    request_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count_runtime = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    installed_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Module(id={self.id}, name='{self.name}', status='{self.status}')>"

    def to_dict(self):
        """Convert module to dictionary for API responses"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "module_type": self.module_type,
            "category": self.category,
            "version": self.version,
            "author": self.author,
            "license": self.license,
            "status": self.status,
            "is_enabled": self.is_enabled,
            "is_core": self.is_core,
            "config_schema": self.config_schema,
            "config_values": self.config_values,
            "default_config": self.default_config,
            "dependencies": self.dependencies,
            "conflicts": self.conflicts,
            "install_path": self.install_path,
            "entry_point": self.entry_point,
            "interceptor_chains": self.interceptor_chains,
            "execution_order": self.execution_order,
            "api_endpoints": self.api_endpoints,
            "required_permissions": self.required_permissions,
            "security_level": self.security_level,
            "tags": self.tags,
            "metadata": self.module_metadata,
            "last_error": self.last_error,
            "error_count": self.error_count,
            "last_started": self.last_started.isoformat()
            if self.last_started
            else None,
            "last_stopped": self.last_stopped.isoformat()
            if self.last_stopped
            else None,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "error_count_runtime": self.error_count_runtime,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "installed_at": self.installed_at.isoformat()
            if self.installed_at
            else None,
            "success_rate": self.get_success_rate(),
            "uptime": self.get_uptime_seconds() if self.is_running() else 0,
        }

    def is_running(self) -> bool:
        """Check if module is currently running"""
        return self.status == ModuleStatus.ACTIVE

    def is_healthy(self) -> bool:
        """Check if module is healthy (running without recent errors)"""
        return self.is_running() and self.error_count_runtime == 0

    def get_success_rate(self) -> float:
        """Get success rate as percentage"""
        if self.request_count == 0:
            return 100.0
        return (self.success_count / self.request_count) * 100

    def get_uptime_seconds(self) -> int:
        """Get uptime in seconds"""
        if not self.last_started:
            return 0
        return int((datetime.utcnow() - self.last_started).total_seconds())

    def can_be_disabled(self) -> bool:
        """Check if module can be disabled"""
        return not self.is_core

    def has_dependency(self, module_name: str) -> bool:
        """Check if module has a specific dependency"""
        return module_name in self.dependencies

    def conflicts_with(self, module_name: str) -> bool:
        """Check if module conflicts with another module"""
        return module_name in self.conflicts

    def requires_permission(self, permission: str) -> bool:
        """Check if module requires a specific permission"""
        return permission in self.required_permissions

    def hooks_into_chain(self, chain_name: str) -> bool:
        """Check if module hooks into a specific interceptor chain"""
        return chain_name in self.interceptor_chains

    def provides_endpoint(self, endpoint: str) -> bool:
        """Check if module provides a specific API endpoint"""
        return endpoint in self.api_endpoints

    def update_config(self, config_updates: Dict[str, Any]):
        """Update module configuration"""
        if self.config_values is None:
            self.config_values = {}
        self.config_values.update(config_updates)
        self.updated_at = datetime.utcnow()

    def reset_config(self):
        """Reset configuration to default values"""
        self.config_values = self.default_config.copy() if self.default_config else {}
        self.updated_at = datetime.utcnow()

    def enable(self):
        """Enable the module"""
        if self.status != ModuleStatus.ERROR:
            self.is_enabled = True
            self.status = ModuleStatus.LOADING
            self.updated_at = datetime.utcnow()

    def disable(self):
        """Disable the module"""
        if self.can_be_disabled():
            self.is_enabled = False
            self.status = ModuleStatus.DISABLED
            self.last_stopped = datetime.utcnow()
            self.updated_at = datetime.utcnow()

    def start(self):
        """Start the module"""
        self.status = ModuleStatus.ACTIVE
        self.last_started = datetime.utcnow()
        self.last_error = None
        self.updated_at = datetime.utcnow()

    def stop(self):
        """Stop the module"""
        self.status = ModuleStatus.INACTIVE
        self.last_stopped = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def set_error(self, error_message: str):
        """Set module error status"""
        self.status = ModuleStatus.ERROR
        self.last_error = error_message
        self.error_count += 1
        self.error_count_runtime += 1
        self.updated_at = datetime.utcnow()

    def clear_error(self):
        """Clear error status"""
        self.last_error = None
        self.error_count_runtime = 0
        self.updated_at = datetime.utcnow()

    def record_request(self, success: bool = True):
        """Record a request to this module"""
        self.request_count += 1
        if success:
            self.success_count += 1
        else:
            self.error_count_runtime += 1

    def add_tag(self, tag: str):
        """Add a tag to the module"""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str):
        """Remove a tag from the module"""
        if tag in self.tags:
            self.tags.remove(tag)

    def update_metadata(self, key: str, value: Any):
        """Update metadata"""
        if self.module_metadata is None:
            self.module_metadata = {}
        self.module_metadata[key] = value

    def add_dependency(self, module_name: str):
        """Add a dependency"""
        if module_name not in self.dependencies:
            self.dependencies.append(module_name)

    def remove_dependency(self, module_name: str):
        """Remove a dependency"""
        if module_name in self.dependencies:
            self.dependencies.remove(module_name)

    def add_conflict(self, module_name: str):
        """Add a conflict"""
        if module_name not in self.conflicts:
            self.conflicts.append(module_name)

    def remove_conflict(self, module_name: str):
        """Remove a conflict"""
        if module_name in self.conflicts:
            self.conflicts.remove(module_name)

    def add_interceptor_chain(self, chain_name: str):
        """Add an interceptor chain"""
        if chain_name not in self.interceptor_chains:
            self.interceptor_chains.append(chain_name)

    def remove_interceptor_chain(self, chain_name: str):
        """Remove an interceptor chain"""
        if chain_name in self.interceptor_chains:
            self.interceptor_chains.remove(chain_name)

    def add_api_endpoint(self, endpoint: str):
        """Add an API endpoint"""
        if endpoint not in self.api_endpoints:
            self.api_endpoints.append(endpoint)

    def remove_api_endpoint(self, endpoint: str):
        """Remove an API endpoint"""
        if endpoint in self.api_endpoints:
            self.api_endpoints.remove(endpoint)

    def add_required_permission(self, permission: str):
        """Add a required permission"""
        if permission not in self.required_permissions:
            self.required_permissions.append(permission)

    def remove_required_permission(self, permission: str):
        """Remove a required permission"""
        if permission in self.required_permissions:
            self.required_permissions.remove(permission)

    @classmethod
    def create_core_module(
        cls,
        name: str,
        display_name: str,
        description: str,
        version: str,
        entry_point: str,
    ) -> "Module":
        """Create a core module"""
        return cls(
            name=name,
            display_name=display_name,
            description=description,
            module_type=ModuleType.CORE,
            version=version,
            author="Confidential Empire",
            license="Proprietary",
            status=ModuleStatus.ACTIVE,
            is_enabled=True,
            is_core=True,
            entry_point=entry_point,
            config_schema={},
            config_values={},
            default_config={},
            dependencies=[],
            conflicts=[],
            interceptor_chains=[],
            execution_order=10,  # Core modules run first
            api_endpoints=[],
            required_permissions=[],
            security_level="high",
            tags=["core"],
            module_metadata={},
        )

    @classmethod
    def create_cache_module(cls) -> "Module":
        """Create the cache module"""
        return cls(
            name="cache",
            display_name="Cache Module",
            description="Redis-based caching for improved performance",
            module_type=ModuleType.INTERCEPTOR,
            category="cache",
            version="1.0.0",
            author="Confidential Empire",
            license="Proprietary",
            status=ModuleStatus.INACTIVE,
            is_enabled=True,
            is_core=False,
            entry_point="app.modules.cache.main",
            config_schema={
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "enum": ["redis"]},
                    "ttl": {"type": "integer", "minimum": 60},
                    "max_size": {"type": "integer", "minimum": 1000},
                },
                "required": ["provider", "ttl"],
            },
            config_values={"provider": "redis", "ttl": 3600, "max_size": 10000},
            default_config={"provider": "redis", "ttl": 3600, "max_size": 10000},
            dependencies=[],
            conflicts=[],
            interceptor_chains=["pre_request", "post_response"],
            execution_order=20,
            api_endpoints=["/api/v1/cache/stats", "/api/v1/cache/clear"],
            required_permissions=["cache.read", "cache.write"],
            security_level="low",
            tags=["cache", "performance"],
            module_metadata={},
        )

    @classmethod
    def create_rag_module(cls) -> "Module":
        """Create the RAG module"""
        return cls(
            name="rag",
            display_name="RAG Module",
            description="Retrieval Augmented Generation with vector database",
            module_type=ModuleType.INTERCEPTOR,
            category="rag",
            version="1.0.0",
            author="Confidential Empire",
            license="Proprietary",
            status=ModuleStatus.INACTIVE,
            is_enabled=True,
            is_core=False,
            entry_point="app.modules.rag.main",
            config_schema={
                "type": "object",
                "properties": {
                    "vector_db": {"type": "string", "enum": ["qdrant"]},
                    "embedding_model": {"type": "string"},
                    "chunk_size": {"type": "integer", "minimum": 100},
                    "max_results": {"type": "integer", "minimum": 1},
                },
                "required": ["vector_db", "embedding_model"],
            },
            config_values={
                "vector_db": "qdrant",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "chunk_size": 512,
                "max_results": 10,
            },
            default_config={
                "vector_db": "qdrant",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "chunk_size": 512,
                "max_results": 10,
            },
            dependencies=[],
            conflicts=[],
            interceptor_chains=["pre_request"],
            execution_order=30,
            api_endpoints=["/api/v1/rag/documents", "/api/v1/rag/search"],
            required_permissions=["rag.read", "rag.write"],
            security_level="medium",
            tags=["rag", "ai", "search"],
            module_metadata={},
        )

    @classmethod
    def create_analytics_module(cls) -> "Module":
        """Create the analytics module"""
        return cls(
            name="analytics",
            display_name="Analytics Module",
            description="Request and response analytics and monitoring",
            module_type=ModuleType.ANALYTICS,
            category="analytics",
            version="1.0.0",
            author="Confidential Empire",
            license="Proprietary",
            status=ModuleStatus.INACTIVE,
            is_enabled=True,
            is_core=False,
            entry_point="app.modules.analytics.main",
            config_schema={
                "type": "object",
                "properties": {
                    "track_requests": {"type": "boolean"},
                    "track_responses": {"type": "boolean"},
                    "retention_days": {"type": "integer", "minimum": 1},
                },
                "required": ["track_requests", "track_responses"],
            },
            config_values={
                "track_requests": True,
                "track_responses": True,
                "retention_days": 30,
            },
            default_config={
                "track_requests": True,
                "track_responses": True,
                "retention_days": 30,
            },
            dependencies=[],
            conflicts=[],
            interceptor_chains=["pre_request", "post_response"],
            execution_order=90,  # Analytics runs last
            api_endpoints=["/api/v1/analytics/stats", "/api/v1/analytics/reports"],
            required_permissions=["analytics.read"],
            security_level="low",
            tags=["analytics", "monitoring"],
            module_metadata={},
        )

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the module"""
        return {
            "name": self.name,
            "status": self.status,
            "is_healthy": self.is_healthy(),
            "success_rate": self.get_success_rate(),
            "uptime_seconds": self.get_uptime_seconds() if self.is_running() else 0,
            "last_error": self.last_error,
            "error_count": self.error_count_runtime,
            "last_started": self.last_started.isoformat()
            if self.last_started
            else None,
        }
