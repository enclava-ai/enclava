"""
Notification models for multi-channel communication
"""
from datetime import datetime
from typing import Optional, Dict, Any
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
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class NotificationType(str, Enum):
    """Notification types"""

    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"
    SMS = "sms"
    PUSH = "push"


class NotificationPriority(str, Enum):
    """Notification priority levels"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationStatus(str, Enum):
    """Notification delivery status"""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"


class NotificationTemplate(Base):
    """Notification template model"""

    __tablename__ = "notification_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Template content
    notification_type = Column(String(20), nullable=False)  # NotificationType enum
    subject_template = Column(Text, nullable=True)  # For email/messages
    body_template = Column(Text, nullable=False)  # Main content
    html_template = Column(Text, nullable=True)  # HTML version for email

    # Configuration
    default_priority = Column(String(20), default=NotificationPriority.NORMAL)
    variables = Column(JSON, default=dict)  # Expected template variables
    template_metadata = Column(JSON, default=dict)  # Additional configuration

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    notifications = relationship("Notification", back_populates="template")

    def __repr__(self):
        return f"<NotificationTemplate(id={self.id}, name='{self.name}', type='{self.notification_type}')>"

    def to_dict(self):
        """Convert template to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "notification_type": self.notification_type,
            "subject_template": self.subject_template,
            "body_template": self.body_template,
            "html_template": self.html_template,
            "default_priority": self.default_priority,
            "variables": self.variables,
            "template_metadata": self.template_metadata,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class NotificationChannel(Base):
    """Notification channel configuration"""

    __tablename__ = "notification_channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)
    notification_type = Column(String(20), nullable=False)  # NotificationType enum

    # Channel configuration
    config = Column(JSON, nullable=False)  # Channel-specific settings
    credentials = Column(JSON, nullable=True)  # Encrypted credentials

    # Settings
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    rate_limit = Column(Integer, default=100)  # Messages per minute
    retry_count = Column(Integer, default=3)
    retry_delay_minutes = Column(Integer, default=5)

    # Health monitoring
    last_used_at = Column(DateTime, nullable=True)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    notifications = relationship("Notification", back_populates="channel")

    def __repr__(self):
        return f"<NotificationChannel(id={self.id}, name='{self.name}', type='{self.notification_type}')>"

    def to_dict(self):
        """Convert channel to dictionary (excluding sensitive credentials)"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "notification_type": self.notification_type,
            "config": self.config,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "rate_limit": self.rate_limit,
            "retry_count": self.retry_count,
            "retry_delay_minutes": self.retry_delay_minutes,
            "last_used_at": self.last_used_at.isoformat()
            if self.last_used_at
            else None,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def update_stats(self, success: bool, error_message: Optional[str] = None):
        """Update channel statistics"""
        self.last_used_at = datetime.utcnow()
        if success:
            self.success_count += 1
            self.last_error = None
        else:
            self.failure_count += 1
            self.last_error = error_message


class Notification(Base):
    """Individual notification instance"""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    # Content
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=False)
    html_body = Column(Text, nullable=True)

    # Recipients
    recipients = Column(JSON, nullable=False)  # List of recipient addresses/IDs
    cc_recipients = Column(JSON, nullable=True)  # CC recipients (for email)
    bcc_recipients = Column(JSON, nullable=True)  # BCC recipients (for email)

    # Configuration
    priority = Column(String(20), default=NotificationPriority.NORMAL)
    scheduled_at = Column(DateTime, nullable=True)  # For scheduled delivery
    expires_at = Column(DateTime, nullable=True)  # Expiration time

    # References
    template_id = Column(
        Integer, ForeignKey("notification_templates.id"), nullable=True
    )
    channel_id = Column(Integer, ForeignKey("notification_channels.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Triggering user

    # Status tracking
    status = Column(String(20), default=NotificationStatus.PENDING)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)

    # Delivery tracking
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # External references
    external_id = Column(String(200), nullable=True)  # Provider message ID
    callback_url = Column(String(500), nullable=True)  # Delivery callback

    # Metadata
    notification_metadata = Column(JSON, default=dict)
    tags = Column(JSON, default=list)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    template = relationship("NotificationTemplate", back_populates="notifications")
    channel = relationship("NotificationChannel", back_populates="notifications")
    user = relationship("User", back_populates="notifications")

    def __repr__(self):
        return f"<Notification(id={self.id}, status='{self.status}', channel='{self.channel.name if self.channel else 'unknown'}')>"

    def to_dict(self):
        """Convert notification to dictionary"""
        return {
            "id": self.id,
            "subject": self.subject,
            "body": self.body,
            "html_body": self.html_body,
            "recipients": self.recipients,
            "cc_recipients": self.cc_recipients,
            "bcc_recipients": self.bcc_recipients,
            "priority": self.priority,
            "scheduled_at": self.scheduled_at.isoformat()
            if self.scheduled_at
            else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "template_id": self.template_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat()
            if self.delivered_at
            else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "error_message": self.error_message,
            "external_id": self.external_id,
            "callback_url": self.callback_url,
            "notification_metadata": self.notification_metadata,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def mark_sent(self, external_id: Optional[str] = None):
        """Mark notification as sent"""
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.utcnow()
        self.external_id = external_id

    def mark_delivered(self):
        """Mark notification as delivered"""
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = datetime.utcnow()

    def mark_failed(self, error_message: str):
        """Mark notification as failed"""
        self.status = NotificationStatus.FAILED
        self.failed_at = datetime.utcnow()
        self.error_message = error_message
        self.attempts += 1

    def can_retry(self) -> bool:
        """Check if notification can be retried"""
        return (
            self.status in [NotificationStatus.FAILED, NotificationStatus.RETRY]
            and self.attempts < self.max_attempts
            and (self.expires_at is None or self.expires_at > datetime.utcnow())
        )
