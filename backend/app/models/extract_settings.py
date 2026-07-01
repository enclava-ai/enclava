"""Extract settings model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.database import Base


class ExtractSettings(Base):
    """
    Global settings for Extract.

    Stores configuration like default model.
    Single-row table (id=1).
    """

    __tablename__ = "extract_settings"

    id = Column(Integer, primary_key=True, default=1)
    default_model = Column(
        String(100), nullable=True
    )  # Auto-selected from available vision models

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<ExtractSettings default_model={self.default_model}>"
