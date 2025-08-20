"""
Database models for Zammad Integration Module
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.database import Base


class TicketState(str, Enum):
    """Zammad ticket state enumeration"""
    NEW = "new"
    OPEN = "open"
    PENDING_REMINDER = "pending reminder"
    PENDING_CLOSE = "pending close"
    CLOSED = "closed"
    MERGED = "merged"
    REMOVED = "removed"


class ProcessingStatus(str, Enum):
    """Ticket processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ZammadTicket(Base):
    """Model for tracking Zammad tickets and their processing status"""
    
    __tablename__ = "zammad_tickets"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Zammad ticket information
    zammad_ticket_id = Column(Integer, unique=True, index=True, nullable=False)
    ticket_number = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    state = Column(String, nullable=False)  # Zammad state
    priority = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    
    # Processing information
    processing_status = Column(String, default=ProcessingStatus.PENDING.value, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    processed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    chatbot_id = Column(String, nullable=True)
    
    # Summary and context
    summary = Column(Text, nullable=True)
    context_data = Column(JSON, nullable=True)  # Original ticket data
    error_message = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Zammad specific metadata
    zammad_created_at = Column(DateTime, nullable=True)
    zammad_updated_at = Column(DateTime, nullable=True)
    zammad_article_count = Column(Integer, default=0, nullable=False)
    
    # Processing configuration snapshot
    config_snapshot = Column(JSON, nullable=True)  # Config used during processing
    
    # Relationships
    processed_by = relationship("User", foreign_keys=[processed_by_user_id])
    
    # Indexes for better query performance
    __table_args__ = (
        Index("idx_zammad_tickets_status_created", "processing_status", "created_at"),
        Index("idx_zammad_tickets_state_processed", "state", "processed_at"),
        Index("idx_zammad_tickets_user_status", "processed_by_user_id", "processing_status"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "zammad_ticket_id": self.zammad_ticket_id,
            "ticket_number": self.ticket_number,
            "title": self.title,
            "state": self.state,
            "priority": self.priority,
            "customer_email": self.customer_email,
            "processing_status": self.processing_status,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "processed_by_user_id": self.processed_by_user_id,
            "chatbot_id": self.chatbot_id,
            "summary": self.summary,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "zammad_created_at": self.zammad_created_at.isoformat() if self.zammad_created_at else None,
            "zammad_updated_at": self.zammad_updated_at.isoformat() if self.zammad_updated_at else None,
            "zammad_article_count": self.zammad_article_count
        }


class ZammadProcessingLog(Base):
    """Model for logging Zammad processing activities"""
    
    __tablename__ = "zammad_processing_logs"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Processing batch information
    batch_id = Column(String, index=True, nullable=False)  # UUID for batch processing
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    initiated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Processing configuration
    config_used = Column(JSON, nullable=True)
    filters_applied = Column(JSON, nullable=True)  # State, limit, etc.
    
    # Results
    tickets_found = Column(Integer, default=0, nullable=False)
    tickets_processed = Column(Integer, default=0, nullable=False)
    tickets_failed = Column(Integer, default=0, nullable=False)
    tickets_skipped = Column(Integer, default=0, nullable=False)
    
    # Performance metrics
    processing_time_seconds = Column(Integer, nullable=True)
    average_time_per_ticket = Column(Integer, nullable=True)  # milliseconds
    
    # Error tracking
    errors_encountered = Column(JSON, nullable=True)  # List of error messages
    status = Column(String, default="running", nullable=False)  # running, completed, failed
    
    # Relationships
    initiated_by = relationship("User", foreign_keys=[initiated_by_user_id])
    
    # Indexes
    __table_args__ = (
        Index("idx_processing_logs_batch_status", "batch_id", "status"),
        Index("idx_processing_logs_user_started", "initiated_by_user_id", "started_at"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "initiated_by_user_id": self.initiated_by_user_id,
            "config_used": self.config_used,
            "filters_applied": self.filters_applied,
            "tickets_found": self.tickets_found,
            "tickets_processed": self.tickets_processed,
            "tickets_failed": self.tickets_failed,
            "tickets_skipped": self.tickets_skipped,
            "processing_time_seconds": self.processing_time_seconds,
            "average_time_per_ticket": self.average_time_per_ticket,
            "errors_encountered": self.errors_encountered,
            "status": self.status
        }


class ZammadConfiguration(Base):
    """Model for storing Zammad module configurations per user"""
    
    __tablename__ = "zammad_configurations"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # User association
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Configuration name and description
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Zammad connection settings
    zammad_url = Column(String, nullable=False)
    api_token_encrypted = Column(String, nullable=False)  # Encrypted API token
    
    # Processing settings
    chatbot_id = Column(String, nullable=False)
    process_state = Column(String, default="open", nullable=False)
    max_tickets = Column(Integer, default=10, nullable=False)
    skip_existing = Column(Boolean, default=True, nullable=False)
    auto_process = Column(Boolean, default=False, nullable=False)
    process_interval = Column(Integer, default=30, nullable=False)  # minutes
    
    # Customization
    summary_template = Column(Text, nullable=True)
    custom_settings = Column(JSON, nullable=True)  # Additional custom settings
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    
    # Indexes
    __table_args__ = (
        Index("idx_zammad_config_user_active", "user_id", "is_active"),
        Index("idx_zammad_config_user_default", "user_id", "is_default"),
    )
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "zammad_url": self.zammad_url,
            "chatbot_id": self.chatbot_id,
            "process_state": self.process_state,
            "max_tickets": self.max_tickets,
            "skip_existing": self.skip_existing,
            "auto_process": self.auto_process,
            "process_interval": self.process_interval,
            "summary_template": self.summary_template,
            "custom_settings": self.custom_settings,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None
        }
        
        if include_sensitive:
            result["api_token_encrypted"] = self.api_token_encrypted
            
        return result