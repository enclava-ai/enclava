"""
Built-in Tool Registry

Central registry for all built-in tools (RAG, web search, code execution).
"""

from typing import Dict, List, Optional
from .base import BuiltinTool


class BuiltinToolRegistry:
    """Registry for built-in tools.

    Returns BuiltinTool instances (not OpenAI schemas) so ToolCallingService
    can convert them uniformly with custom Tool objects.

    Usage:
        # Register a tool at startup
        BuiltinToolRegistry.register(RAGSearchTool())

        # Get a tool by name
        tool = BuiltinToolRegistry.get("rag_search")

        # Get all tools
        all_tools = BuiltinToolRegistry.get_all()

        # Check if a tool is built-in
        is_builtin = BuiltinToolRegistry.is_builtin("rag_search")
    """

    _tools: Dict[str, BuiltinTool] = {}

    @classmethod
    def register(cls, tool: BuiltinTool):
        """Register a built-in tool.

        Args:
            tool: BuiltinTool instance to register

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        if tool.name in cls._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")

        cls._tools[tool.name] = tool

    @classmethod
    def get(cls, name: str) -> Optional[BuiltinTool]:
        """Get a built-in tool by name.

        Args:
            name: Tool name

        Returns:
            BuiltinTool instance or None if not found
        """
        return cls._tools.get(name)

    @classmethod
    def get_all(cls) -> List[BuiltinTool]:
        """Return all registered tools as BuiltinTool instances.

        NOTE: Returns tool objects, NOT OpenAI schemas. Conversion happens
        in ToolCallingService._convert_tools_to_openai_format to avoid
        double-conversion.

        Returns:
            List of all registered BuiltinTool instances
        """
        return list(cls._tools.values())

    @classmethod
    def is_builtin(cls, name: str) -> bool:
        """Check if a tool is a built-in tool.

        Args:
            name: Tool name to check

        Returns:
            True if the tool is registered as a built-in tool
        """
        return name in cls._tools

    @classmethod
    def clear(cls):
        """Clear all registered tools.

        This is primarily for testing purposes.
        """
        cls._tools.clear()
