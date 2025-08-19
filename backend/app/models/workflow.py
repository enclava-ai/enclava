"""
Database models for workflow module
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid
import enum

from app.db.database import Base


class WorkflowStatus(enum.Enum):
    """Workflow execution statuses"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowDefinition(Base):
    """Workflow definition/template"""
    __tablename__ = "workflow_definitions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text)
    version = Column(String(50), default="1.0.0")
    
    # Workflow definition stored as JSON
    steps = Column(JSON, nullable=False)
    variables = Column(JSON, default={})
    workflow_metadata = Column("metadata", JSON, default={})
    
    # Configuration
    timeout = Column(Integer)  # Timeout in seconds
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_by = Column(String, nullable=False)  # User ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    executions = relationship("WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WorkflowDefinition(id='{self.id}', name='{self.name}')>"


class WorkflowExecution(Base):
    """Workflow execution instance"""
    __tablename__ = "workflow_executions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, ForeignKey("workflow_definitions.id"), nullable=False)
    
    # Execution state
    status = Column(SQLEnum(WorkflowStatus), default=WorkflowStatus.PENDING)
    current_step = Column(String)  # Current step ID
    
    # Execution data
    input_data = Column(JSON, default={})
    context = Column(JSON, default={})
    results = Column(JSON, default={})
    error = Column(Text)
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Metadata
    executed_by = Column(String, nullable=False)  # User ID or system
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workflow = relationship("WorkflowDefinition", back_populates="executions")
    step_logs = relationship("WorkflowStepLog", back_populates="execution", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WorkflowExecution(id='{self.id}', workflow_id='{self.workflow_id}', status='{self.status}')>"


class WorkflowStepLog(Base):
    """Individual step execution log"""
    __tablename__ = "workflow_step_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String, ForeignKey("workflow_executions.id"), nullable=False)
    
    # Step information
    step_id = Column(String, nullable=False)
    step_name = Column(String(255), nullable=False)
    step_type = Column(String(50), nullable=False)
    
    # Execution details
    status = Column(String(50), nullable=False)  # started, completed, failed
    input_data = Column(JSON, default={})
    output_data = Column(JSON, default={})
    error = Column(Text)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)  # Duration in milliseconds
    
    # Metadata
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    execution = relationship("WorkflowExecution", back_populates="step_logs")
    
    def __repr__(self):
        return f"<WorkflowStepLog(id='{self.id}', step_name='{self.step_name}', status='{self.status}')>"