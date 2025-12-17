"""
RAG Search Built-in Tool

Searches the knowledge base for relevant information using the RAG module.
"""

from typing import Dict, Any
from .base import BuiltinTool, ToolExecutionContext, ToolResult


class RAGSearchTool(BuiltinTool):
    """Built-in tool for searching the RAG knowledge base.

    This tool integrates with the existing RAG module to search for
    relevant documents and information from the vector database.

    Attributes:
        name: "rag_search" - unique identifier for the tool
        display_name: "RAG Search" - human-readable name
        description: Description for the LLM to understand when to use this tool
        parameters_schema: JSON Schema for the query and max_results parameters
    """

    name = "rag_search"
    display_name = "RAG Search"  # Required by _convert_tools_to_openai_format
    description = "Search the knowledge base for relevant information using vector similarity"
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant documents"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "default": 5,
                "minimum": 1,
                "maximum": 20
            }
        },
        "required": ["query"]
    }

    async def execute(self, params: Dict[str, Any], ctx: ToolExecutionContext) -> ToolResult:
        """Execute RAG search with the given query.

        Args:
            params: Dictionary containing:
                - query (str): Search query
                - max_results (int, optional): Max results to return (default: 5)
            ctx: Execution context with user_id and db session

        Returns:
            ToolResult with search results or error
        """
        try:
            from app.modules.rag.main import RAGModule

            # Initialize RAG module
            rag = RAGModule()

            # Check if RAG is enabled
            if not rag.enabled:
                return ToolResult(
                    success=False,
                    output=None,
                    error="RAG module is not initialized or enabled"
                )

            # Extract parameters
            query = params.get("query")
            if not query:
                return ToolResult(
                    success=False,
                    output=None,
                    error="Query parameter is required"
                )

            max_results = params.get("max_results", 5)

            # Execute search
            # Note: RAG module doesn't currently support user_id filtering
            # If user-specific filtering is needed, it can be added via filters parameter
            results = await rag.search_documents(
                query=query,
                max_results=max_results
            )

            # Format results for LLM consumption
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "content": result.document.content[:500],  # Truncate for brevity
                    "score": result.score,
                    "relevance": result.relevance_score,
                    "filename": result.document.original_filename,
                    "file_type": result.document.file_type,
                    "metadata": result.document.metadata
                })

            return ToolResult(
                success=True,
                output={
                    "results": formatted_results,
                    "count": len(formatted_results),
                    "query": query
                }
            )

        except RuntimeError as e:
            # RAG module raises RuntimeError when not enabled
            return ToolResult(
                success=False,
                output=None,
                error=f"RAG module error: {str(e)}"
            )
        except Exception as e:
            # Catch any other errors
            return ToolResult(
                success=False,
                output=None,
                error=f"RAG search failed: {str(e)}"
            )
