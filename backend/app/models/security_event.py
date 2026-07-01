"""
Legacy security event model used by older threat-detection tests.
"""

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.db.database import Base, utc_now


class SecurityEvent(Base):
    """Security event record for suspicious request/activity tracking."""

    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    client_ip = Column(String, nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    payload = Column(Text, nullable=True)
    risk_score = Column(Float, default=0.0)
    blocked = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=utc_now, index=True)
