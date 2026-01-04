"""
RAG Search Built-in Tool

Enhanced multi-collection RAG search with result merging, deduplication,
and token budget management (OpenAI file_search compatible).
"""

import hashlib
import logging
from typing import Dict, Any, List, Optional
from .base import BuiltinTool, ToolExecutionContext, ToolResult

logger = logging.getLogger(__name__)

# Global limits (non-overridable for safety)
MAX_COLLECTIONS_PER_AGENT = 5
MAX_TOTAL_RESULTS = 20
MAX_RESULT_CONTENT_CHARS = 2000

# Default limits (configurable per request)
DEFAULT_TOP_K = 5
DEFAULT_TOP_K_PER_COLLECTION = 3
DEFAULT_SCORE_THRESHOLD = 0.5


class RAGSearchTool(BuiltinTool):
    """Built-in tool for searching the RAG knowledge base.

    Enhanced to support multiple collections (vector stores) with:
    - Multi-collection search and result merging
    - Deduplication by content hash
    - Configurable limits and score thresholds
    - Token budget estimation

    Maps to OpenAI's file_search tool concept where:
    - Collections = Vector Stores
    - Searches all attached collections
    - Merges and ranks results by relevance

    Attributes:
        name: "rag_search" - unique identifier for the tool
        display_name: "RAG Search" - human-readable name
        description: Description for the LLM to understand when to use this tool
        parameters_schema: JSON Schema for the query and configuration parameters
    """

    name = "rag_search"
    display_name = "RAG Search"
    description = """Search the internal knowledge base for information from uploaded documents and configured vector stores.

USE THIS TOOL WHEN:
- User asks about content from uploaded files, documents, or internal knowledge
- Searching company/project-specific information stored in the knowledge base
- Looking up information from the configured vector stores (collections)
- User explicitly mentions "knowledge base", "documents", or "uploaded files"

DO NOT USE THIS TOOL WHEN:
- User asks about external websites, public GitHub repos, or public information
- Real-time data is needed (news, current events, live data)
- An MCP tool (like deepwiki for GitHub) is better suited for the query
- User is asking about general knowledge not in the uploaded documents"""
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant documents"
            },
            "vector_store_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of collection/vector store IDs to search (max 5)",
                "default": []
            },
            "max_results": {
                "type": "integer",
                "description": f"Maximum total results to return (max {MAX_TOTAL_RESULTS})",
                "default": DEFAULT_TOP_K,
                "minimum": 1,
                "maximum": MAX_TOTAL_RESULTS
            },
            "max_results_per_collection": {
                "type": "integer",
                "description": "Maximum results per collection",
                "default": DEFAULT_TOP_K_PER_COLLECTION,
                "minimum": 1,
                "maximum": 10
            },
            "score_threshold": {
                "type": "number",
                "description": "Minimum relevance score threshold (0.0-1.0)",
                "default": DEFAULT_SCORE_THRESHOLD,
                "minimum": 0.0,
                "maximum": 1.0
            }
        },
        "required": ["query"]
    }

    async def execute(self, params: Dict[str, Any], ctx: ToolExecutionContext) -> ToolResult:
        """Execute enhanced RAG search with multi-collection support.

        Flow:
        1. Validate and extract parameters
        2. Search each collection independently
        3. Merge results and deduplicate
        4. Sort by score and apply limits
        5. Truncate content to token budget
        6. Return formatted results

        Args:
            params: Dictionary containing:
                - query (str): Search query
                - vector_store_ids (list, optional): Collection IDs to search
                - max_results (int, optional): Max total results (default: 5)
                - max_results_per_collection (int, optional): Max per collection (default: 3)
                - score_threshold (float, optional): Min score (default: 0.5)
            ctx: Execution context with user_id and db session

        Returns:
            ToolResult with merged, deduplicated search results
        """
        try:
            from app.services.module_manager import module_manager

            # Get RAG module from module manager (properly initialized singleton)
            if "rag" not in module_manager.modules:
                return ToolResult(
                    success=False,
                    output=None,
                    error="RAG module is not loaded. Please ensure the RAG module is enabled."
                )

            rag = module_manager.modules["rag"]

            # Check if RAG is enabled
            if not rag.enabled:
                return ToolResult(
                    success=False,
                    output=None,
                    error="RAG module is not initialized or enabled"
                )

            # Extract and validate parameters
            query = params.get("query")
            if not query:
                return ToolResult(
                    success=False,
                    output=None,
                    error="Query parameter is required"
                )

            # Get collections to search
            # Priority: 1. LLM-provided vector_store_ids, 2. Agent's tool_resources config
            vector_store_ids = params.get("vector_store_ids", [])

            # Fallback to tool_resources from agent config if not provided by LLM
            file_search_config = {}
            if ctx.tool_resources:
                file_search_config = ctx.tool_resources.get("file_search", {})

            if not vector_store_ids and file_search_config:
                vector_store_ids = file_search_config.get("vector_store_ids", [])
                if vector_store_ids:
                    logger.info(f"Using collections from agent config: {vector_store_ids}")

            # Enforce collection limit
            if len(vector_store_ids) > MAX_COLLECTIONS_PER_AGENT:
                vector_store_ids = vector_store_ids[:MAX_COLLECTIONS_PER_AGENT]

            # Get limits - prefer LLM params, then agent config, then defaults
            config_max_results = file_search_config.get("max_results", DEFAULT_TOP_K)
            max_results = min(
                params.get("max_results", config_max_results),
                MAX_TOTAL_RESULTS
            )
            max_per_collection = min(
                params.get("max_results_per_collection", DEFAULT_TOP_K_PER_COLLECTION),
                10
            )
            score_threshold = params.get("score_threshold", DEFAULT_SCORE_THRESHOLD)

            # Search collections
            all_results = []
            collections_searched = []

            if vector_store_ids:
                # Search specific collections
                for collection_id in vector_store_ids:
                    try:
                        results = await rag.search_documents(
                            query=query,
                            max_results=max_per_collection,
                            collection_name=collection_id  # If supported
                        )
                        all_results.extend(results)
                        collections_searched.append(collection_id)
                    except Exception as e:
                        # Log but continue with other collections
                        logger.warning(f"Error searching collection {collection_id}: {e}")
            else:
                # Search default collection
                results = await rag.search_documents(
                    query=query,
                    max_results=max_results
                )
                all_results.extend(results)
                collections_searched.append("default")

            # Filter by score threshold
            all_results = [r for r in all_results if r.score >= score_threshold]

            # Deduplicate by content hash
            deduplicated_results = self._deduplicate_results(all_results)

            # Sort by score (descending)
            deduplicated_results.sort(key=lambda r: r.score, reverse=True)

            # Limit total results
            final_results = deduplicated_results[:max_results]

            # Format results with content truncation
            formatted_results = []
            for result in final_results:
                content = result.document.content

                # Truncate to token budget
                if len(content) > MAX_RESULT_CONTENT_CHARS:
                    content = content[:MAX_RESULT_CONTENT_CHARS] + "..."

                # Get filename and file_type from metadata (Document class stores these there)
                metadata = result.document.metadata or {}
                filename = metadata.get("original_filename") or metadata.get("filename") or metadata.get("source", "unknown")
                file_type = metadata.get("file_type") or metadata.get("type", "unknown")

                formatted_results.append({
                    "content": content,
                    "score": result.score,
                    "relevance": result.relevance_score,
                    "filename": filename,
                    "file_type": file_type,
                    "metadata": metadata,
                    "collection_id": getattr(result, 'collection_id', 'default')
                })

            # Estimate token usage
            estimated_tokens = self._estimate_token_usage(formatted_results)

            return ToolResult(
                success=True,
                output={
                    "results": formatted_results,
                    "count": len(formatted_results),
                    "collections_searched": collections_searched,
                    "query": query,
                    "estimated_tokens": estimated_tokens,
                    "total_results_found": len(all_results),
                    "results_after_dedup": len(deduplicated_results)
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
            logger.error(f"RAG search failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                output=None,
                error=f"RAG search failed: {str(e)}"
            )

    def _deduplicate_results(self, results: List[Any]) -> List[Any]:
        """Deduplicate results by content hash.

        Args:
            results: List of search results

        Returns:
            Deduplicated results (keeping highest scoring duplicate)
        """
        seen_hashes = {}
        deduplicated = []

        for result in results:
            # Create content hash
            content = result.document.content
            content_hash = hashlib.md5(content.encode()).hexdigest()

            # Keep first occurrence (or highest scoring if sorted first)
            if content_hash not in seen_hashes:
                seen_hashes[content_hash] = True
                deduplicated.append(result)

        return deduplicated

    def _estimate_token_usage(self, formatted_results: List[Dict[str, Any]]) -> int:
        """Estimate token usage for search results.

        Rough estimation: ~4 characters per token

        Args:
            formatted_results: List of formatted search results

        Returns:
            Estimated token count
        """
        total_chars = 0

        for result in formatted_results:
            # Count content characters
            content = result.get("content", "")
            total_chars += len(content)

            # Add overhead for metadata
            total_chars += 100  # Approximate overhead per result

        # Convert to tokens (rough estimate)
        return total_chars // 4
