"""
Prompt Template Models for customizable chatbot prompts
"""

from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer
from sqlalchemy.sql import func
from app.db.database import Base
from datetime import datetime


class PromptTemplate(Base):
    """Editable prompt templates for different chatbot types"""

    __tablename__ = "prompt_templates"

    id = Column(String, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)  # Human readable name
    type_key = Column(
        String(100), nullable=False, unique=True, index=True
    )  # assistant, customer_support, etc.
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=False)
    is_default = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<PromptTemplate(type_key='{self.type_key}', name='{self.name}')>"


class ChatbotPromptVariable(Base):
    """Available variables that can be used in prompts"""

    __tablename__ = "prompt_variables"

    id = Column(String, primary_key=True, index=True)
    variable_name = Column(
        String(100), nullable=False, unique=True, index=True
    )  # {user_name}, {context}, etc.
    description = Column(Text, nullable=True)
    example_value = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<PromptVariable(name='{self.variable_name}')>"
