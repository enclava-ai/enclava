"""
Built-in Tools Package

This package contains built-in tools that are available to all users:
- RAGSearchTool: Search the knowledge base
- WebSearchTool: Search the internet via Brave API
- CodeExecutionTool: Execute Python code in a sandboxed environment

Tools are registered at application startup via register_builtin_tools().
"""

from .base import BuiltinTool, ToolExecutionContext, ToolResult
from .registry import BuiltinToolRegistry
from .rag_search import RAGSearchTool
from .web_search import WebSearchTool
from .code_execution import CodeExecutionTool


def register_builtin_tools():
    """Register all built-in tools with the BuiltinToolRegistry.

    This function should be called once at application startup,
    typically from app.main.py after FastAPI initialization.

    Tools are registered as instances (not classes) so they can
    be retrieved and executed later via the registry.
    """
    # Clear any existing registrations (useful for testing)
    BuiltinToolRegistry.clear()

    # Register built-in tools
    BuiltinToolRegistry.register(RAGSearchTool())
    BuiltinToolRegistry.register(WebSearchTool())
    BuiltinToolRegistry.register(CodeExecutionTool())


__all__ = [
    "BuiltinTool",
    "ToolExecutionContext",
    "ToolResult",
    "BuiltinToolRegistry",
    "RAGSearchTool",
    "WebSearchTool",
    "CodeExecutionTool",
    "register_builtin_tools",
]
