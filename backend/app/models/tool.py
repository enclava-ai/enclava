"""
Tool model for custom tool execution
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    Float,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class ToolType(str, Enum):
    """Tool execution types"""

    PYTHON = "python"
    BASH = "bash"
    DOCKER = "docker"
    API = "api"
    CUSTOM = "custom"


class ToolStatus(str, Enum):
    """Tool execution status"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class Tool(Base):
    """Tool definition model"""

    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Tool configuration
    tool_type = Column(String(20), nullable=False)  # ToolType enum
    code = Column(Text, nullable=False)  # Tool implementation code
    parameters_schema = Column(JSON, default=dict)  # JSON schema for parameters
    return_schema = Column(JSON, default=dict)  # Expected return format

    # Execution settings
    timeout_seconds = Column(Integer, default=30)
    max_memory_mb = Column(Integer, default=256)
    max_cpu_seconds = Column(Float, default=10.0)

    # Docker settings (for docker type tools)
    docker_image = Column(String(200), nullable=True)
    docker_command = Column(Text, nullable=True)

    # Access control
    is_public = Column(Boolean, default=False)  # Public tools available to all users
    is_approved = Column(Boolean, default=False)  # Admin approved for security
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Categories and tags
    category = Column(String(50), nullable=True)
    tags = Column(JSON, default=list)

    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    created_by = relationship("User", back_populates="created_tools")
    executions = relationship(
        "ToolExecution", back_populates="tool", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Tool(id={self.id}, name='{self.name}', type='{self.tool_type}')>"

    def to_dict(self):
        """Convert tool to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "tool_type": self.tool_type,
            "parameters_schema": self.parameters_schema,
            "return_schema": self.return_schema,
            "timeout_seconds": self.timeout_seconds,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_seconds": self.max_cpu_seconds,
            "docker_image": self.docker_image,
            "is_public": self.is_public,
            "is_approved": self.is_approved,
            "created_by_user_id": self.created_by_user_id,
            "category": self.category,
            "tags": self.tags,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat()
            if self.last_used_at
            else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def increment_usage(self):
        """Increment usage count and update last used timestamp"""
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()

    def can_be_used_by(self, user) -> bool:
        """Check if user can use this tool"""
        # Tool creator can always use their tools
        if self.created_by_user_id == user.id:
            return True

        # Public and approved tools can be used by anyone
        if self.is_public and self.is_approved:
            return True

        # Admin users can use any tool
        if user.has_permission("manage_tools"):
            return True

        return False


class ToolExecution(Base):
    """Tool execution instance model"""

    __tablename__ = "tool_executions"

    id = Column(Integer, primary_key=True, index=True)

    # Tool and user references
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    executed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Execution details
    parameters = Column(JSON, default=dict)  # Input parameters
    status = Column(String(20), nullable=False, default=ToolStatus.PENDING)

    # Results
    output = Column(Text, nullable=True)  # Tool output
    error_message = Column(Text, nullable=True)  # Error details if failed
    return_code = Column(Integer, nullable=True)  # Exit code

    # Resource usage
    execution_time_ms = Column(Integer, nullable=True)  # Actual execution time
    memory_used_mb = Column(Float, nullable=True)  # Peak memory usage
    cpu_time_ms = Column(Integer, nullable=True)  # CPU time used

    # Docker execution details
    container_id = Column(String(100), nullable=True)  # Docker container ID
    docker_logs = Column(Text, nullable=True)  # Docker container logs

    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tool = relationship("Tool", back_populates="executions")
    executed_by = relationship("User", back_populates="tool_executions")

    def __repr__(self):
        return f"<ToolExecution(id={self.id}, tool_id={self.tool_id}, status='{self.status}')>"

    def to_dict(self):
        """Convert execution to dictionary"""
        return {
            "id": self.id,
            "tool_id": self.tool_id,
            "tool_name": self.tool.name if self.tool else None,
            "executed_by_user_id": self.executed_by_user_id,
            "parameters": self.parameters,
            "status": self.status,
            "output": self.output,
            "error_message": self.error_message,
            "return_code": self.return_code,
            "execution_time_ms": self.execution_time_ms,
            "memory_used_mb": self.memory_used_mb,
            "cpu_time_ms": self.cpu_time_ms,
            "container_id": self.container_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def duration_seconds(self) -> float:
        """Calculate execution duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    def is_running(self) -> bool:
        """Check if execution is currently running"""
        return self.status in [ToolStatus.PENDING, ToolStatus.RUNNING]

    def is_finished(self) -> bool:
        """Check if execution is finished (success or failure)"""
        return self.status in [
            ToolStatus.COMPLETED,
            ToolStatus.FAILED,
            ToolStatus.TIMEOUT,
            ToolStatus.CANCELLED,
        ]


class ToolCategory(Base):
    """Tool category for organization"""

    __tablename__ = "tool_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Visual
    icon = Column(String(50), nullable=True)  # Icon name
    color = Column(String(20), nullable=True)  # Color code

    # Ordering
    sort_order = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ToolCategory(id={self.id}, name='{self.name}')>"

    def to_dict(self):
        """Convert category to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
