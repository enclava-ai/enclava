"""Extract processing job model."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ExtractJob(Base):
    """
    Extract processing job tracking.

    Tracks the lifecycle of a document processing request from upload
    through extraction and validation.

    Status flow: pending -> processing -> completed | failed

    Attributes:
        id: Unique job identifier
        user_id: User who created the job
        api_key_id: API key used (if API request, null for JWT request)
        filename: Sanitized filename for storage
        original_filename: User's original filename
        file_type: File extension (pdf, jpg, png)
        file_size: File size in bytes
        num_pages: Number of pages (for PDFs)
        status: Job status (pending, processing, completed, failed)
        template_id: Template used for extraction
        buyer_context: Optional context dict as JSON string (for template placeholders)
        model_used: Vision model used for extraction
        prompt_tokens: Input tokens used
        completion_tokens: Output tokens used
        total_cost_cents: Cost in cents for this job
        error_message: Error details if failed
    """

    __tablename__ = "extract_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # User tracking
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)

    # File metadata
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    num_pages = Column(Integer, default=1)

    # Processing state
    status = Column(String(50), nullable=False, default="pending", index=True)
    template_id = Column(
        String(100), ForeignKey("extract_templates.id"), nullable=False
    )
    buyer_context = Column(Text, nullable=True)
    model_used = Column(String(100), nullable=True)

    # Token usage (for job-level reporting)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_cost_cents = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="extract_jobs")
    api_key = relationship("APIKey")
    template = relationship("ExtractTemplate")
    results = relationship(
        "ExtractResult", back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ExtractJob {self.id}: {self.status}>"
