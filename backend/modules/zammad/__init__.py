"""
Zammad Integration Module for Enclava Platform

AI-powered ticket summarization for Zammad ticketing system.
Replaces Ollama with Enclava's chatbot system for enhanced security and flexibility.
"""

from .main import ZammadModule

__version__ = "1.0.0"
__author__ = "Enclava Platform"

__all__ = ["ZammadModule"]