"""
Chatbot Module - AI Chatbot with RAG Integration

This module provides AI chatbot capabilities with:
- Multiple personality types (Assistant, Customer Support, Teacher, etc.)
- RAG integration for knowledge-based responses
- Conversation memory and context management
- Workflow integration as building blocks
- UI-configurable settings
"""

from .main import ChatbotModule, create_module

__version__ = "1.0.0"
__author__ = "Enclava Team"

# Export main classes for easy importing
__all__ = [
    "ChatbotModule", 
    "create_module"
]