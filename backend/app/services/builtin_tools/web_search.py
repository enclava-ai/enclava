"""
Web Search Built-in Tool

Searches the internet for current information using Brave Search API.
"""

import os
import aiohttp
from typing import Dict, Any
from .base import BuiltinTool, ToolExecutionContext, ToolResult


class WebSearchTool(BuiltinTool):
    """Built-in tool for searching the internet via Brave Search API.

    This tool enables LLMs to search for current information, news,
    and real-time data from the web.

    Requires BRAVE_SEARCH_API_KEY environment variable to be set.

    Attributes:
        name: "web_search" - unique identifier for the tool
        display_name: "Web Search" - human-readable name
        description: Description for the LLM to understand when to use this tool
        parameters_schema: JSON Schema for the query and num_results parameters
    """

    name = "web_search"
    display_name = "Web Search"  # Required by _convert_tools_to_openai_format
    description = """Search the public internet for current information, news, and real-time data.

USE THIS TOOL WHEN:
- User needs real-time or current information (news, weather, live data)
- Looking up public websites, documentation, or general web content
- No specific MCP tool is configured for the data source
- User asks about topics not covered by internal documents or specialized tools

DO NOT USE THIS TOOL WHEN:
- User asks about internal documents or uploaded files (use rag_search instead)
- A specialized MCP tool exists for that data source (e.g., deepwiki for GitHub repos)
- The information is already available in the conversation context"""
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find information on the web"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of search results to return (default: 5)",
                "default": 5,
                "minimum": 1,
                "maximum": 20
            }
        },
        "required": ["query"]
    }

    async def execute(self, params: Dict[str, Any], ctx: ToolExecutionContext) -> ToolResult:
        """Execute web search with the given query.

        Args:
            params: Dictionary containing:
                - query (str): Search query
                - num_results (int, optional): Number of results to return (default: 5)
            ctx: Execution context (not used for web search)

        Returns:
            ToolResult with search results or error
        """
        # Check for API key
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                output=None,
                error="Brave Search API key not configured. Set BRAVE_SEARCH_API_KEY environment variable."
            )

        # Extract parameters
        query = params.get("query")
        if not query:
            return ToolResult(
                success=False,
                output=None,
                error="Query parameter is required"
            )

        num_results = params.get("num_results", 5)

        try:
            # Make API request to Brave Search
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={
                        "q": query,
                        "count": num_results
                    },
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": api_key
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return ToolResult(
                            success=False,
                            output=None,
                            error=f"Brave Search API error (status {resp.status}): {error_text}"
                        )

                    data = await resp.json()

                    # Extract and format results
                    web_results = data.get("web", {}).get("results", [])
                    formatted_results = []

                    for result in web_results:
                        formatted_results.append({
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "description": result.get("description", ""),
                            "age": result.get("age"),  # How recent the result is
                            "extra_snippets": result.get("extra_snippets", [])
                        })

                    return ToolResult(
                        success=True,
                        output={
                            "results": formatted_results,
                            "count": len(formatted_results),
                            "query": query
                        }
                    )

        except aiohttp.ClientError as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Network error during web search: {str(e)}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Web search failed: {str(e)}"
            )
