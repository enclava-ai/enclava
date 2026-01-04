"""
MCP (Model Context Protocol) Client

Client for calling external MCP servers using JSON-RPC 2.0 protocol.
Supports both JSON and SSE (Server-Sent Events) response formats.
Normalizes tool formats between MCP and OpenAI function calling format.
"""

import asyncio
import aiohttp
import json
import uuid
from typing import Dict, List, Any, Optional

from app.core.logging import get_logger

logger = get_logger("mcp_client")


class MCPClient:
    """Client for calling MCP servers using JSON-RPC 2.0 protocol.

    MCP (Model Context Protocol) uses JSON-RPC 2.0 for communication.
    All requests go to the server URL with method names in the body.

    This client normalizes MCP tool format to OpenAI function calling format:
    - MCP format: {name, description, inputSchema}
    - OpenAI format: {type: "function", function: {name, description, parameters}}
    """

    def __init__(
        self,
        server_url: str,
        api_key: Optional[str] = None,
        api_key_header_name: str = "Authorization",
        timeout_seconds: int = 30,
        max_retries: int = 3
    ):
        """Initialize MCP client.

        Args:
            server_url: Full URL of the MCP server endpoint (e.g., https://mcp.example.com/mcp)
            api_key: Optional API key for authentication
            api_key_header_name: HTTP header name for API key (default: "Authorization")
                Common values: "Authorization", "X-API-Key", "Api-Key", "X-Auth-Token"
            timeout_seconds: Request timeout in seconds (default: 30)
            max_retries: Maximum retry attempts (default: 3)
        """
        # Don't strip trailing slash - URL should be used as-is
        self.server_url = server_url
        self.api_key = api_key
        self.api_key_header_name = api_key_header_name
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        # Session ID will be assigned by server during initialize
        self.session_id: Optional[str] = None
        self._initialized = False
        self._initialization_attempted = False
        self._initialization_error: Optional[str] = None

    async def _ensure_initialized(self) -> None:
        """Ensure the MCP session is initialized before making calls.

        Raises:
            RuntimeError: If initialization fails due to connection issues
                         after max retries are exhausted.
        """
        if self._initialized:
            return

        # If we've already tried and failed, raise the stored error
        if self._initialization_attempted and self._initialization_error:
            raise RuntimeError(
                f"MCP initialization previously failed: {self._initialization_error}"
            )

        self._initialization_attempted = True

        try:
            # MCP protocol requires initialize call to establish session
            # Don't send session ID on first request - server will assign one
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
            if self.api_key:
                if self.api_key_header_name.lower() == "authorization":
                    headers[self.api_key_header_name] = f"Bearer {self.api_key}"
                else:
                    headers[self.api_key_header_name] = self.api_key

            payload = self._make_jsonrpc_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "enclava",
                    "version": "1.0.0"
                }
            })

            logger.info(f"MCP initialize request to {self.server_url}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.server_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
                ) as resp:
                    # Capture session ID from response headers - this is required
                    server_session_id = resp.headers.get("Mcp-Session-Id")
                    if server_session_id:
                        self.session_id = server_session_id
                        logger.info(f"MCP session established: {self.session_id}")

                    if resp.status == 200:
                        # Handle SSE or JSON response
                        content_type = resp.headers.get("Content-Type", "")
                        if "text/event-stream" in content_type:
                            data = await self._parse_sse_response(resp)
                        else:
                            data = await resp.json()
                        logger.debug(f"MCP initialize response: {data}")
                        self._initialized = True
                        self._initialization_error = None
                    elif resp.status in (401, 403):
                        # Authentication failure - don't retry, surface immediately
                        error_text = await resp.text()
                        self._initialization_error = f"Authentication failed ({resp.status}): {error_text}"
                        logger.error(f"MCP authentication failed: {self._initialization_error}")
                        raise RuntimeError(self._initialization_error)
                    else:
                        # Non-200 but server responded - some servers don't require initialize
                        error_text = await resp.text()
                        logger.warning(f"MCP initialize returned {resp.status}: {error_text}")
                        # Mark as initialized since server is reachable
                        self._initialized = True
                        self._initialization_error = None

        except aiohttp.ClientError as e:
            # Network/connection errors - store for debuggability and raise
            self._initialization_error = f"Connection failed: {e}"
            logger.error(f"MCP initialize connection failed: {self._initialization_error}")
            raise RuntimeError(self._initialization_error) from e
        except asyncio.TimeoutError as e:
            # Timeout - store for debuggability and raise
            self._initialization_error = f"Connection timed out after {self.timeout_seconds}s"
            logger.error(f"MCP initialize timeout: {self._initialization_error}")
            raise RuntimeError(self._initialization_error) from e
        except RuntimeError:
            # Re-raise RuntimeError (auth failures) as-is
            raise
        except Exception as e:
            # Unexpected errors - log and store but allow retry
            self._initialization_error = f"Unexpected error: {e}"
            logger.warning(f"MCP initialize failed unexpectedly: {e}")
            # Reset attempted flag to allow retry for unexpected errors
            self._initialization_attempted = False
            raise RuntimeError(self._initialization_error) from e

    async def _parse_sse_response(self, resp: aiohttp.ClientResponse) -> Any:
        """Parse Server-Sent Events response from MCP server.

        SSE format:
            event: message
            data: {"jsonrpc": "2.0", "result": {...}, "id": "..."}

        Args:
            resp: The aiohttp response object

        Returns:
            Parsed JSON-RPC result from the SSE stream
        """
        result = None
        async for line in resp.content:
            line = line.decode('utf-8').strip()
            if line.startswith('data:'):
                data_str = line[5:].strip()
                if data_str:
                    try:
                        data = json.loads(data_str)
                        # Check for JSON-RPC response
                        if "result" in data:
                            result = data.get("result", data)
                        elif "error" in data:
                            error = data["error"]
                            error_msg = error.get("message", str(error))
                            error_code = error.get("code", "unknown")
                            raise RuntimeError(f"MCP error ({error_code}): {error_msg}")
                    except json.JSONDecodeError:
                        continue
        return result

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers including authentication and session ID.

        For "Authorization" header, uses "Bearer <key>" format.
        For other headers (X-API-Key, etc.), uses raw key value.

        Returns:
            Dict with Content-Type, Accept, session ID, and auth headers.
        """
        headers = {
            "Content-Type": "application/json",
            # MCP servers may use SSE for streaming, so accept both formats
            "Accept": "application/json, text/event-stream",
        }

        # Add session ID if we have one (assigned by server during initialize)
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        if self.api_key:
            if self.api_key_header_name.lower() == "authorization":
                headers[self.api_key_header_name] = f"Bearer {self.api_key}"
            else:
                # For custom headers like X-API-Key, CONTEXT7_API_KEY, use raw value
                headers[self.api_key_header_name] = self.api_key

        return headers

    def _make_jsonrpc_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a JSON-RPC 2.0 request object.

        Args:
            method: The RPC method name (e.g., "tools/list", "tools/call")
            params: Optional parameters for the method

        Returns:
            JSON-RPC 2.0 request dict
        """
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": str(uuid.uuid4())
        }
        if params is not None:
            request["params"] = params
        return request

    async def _send_request_raw(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a JSON-RPC 2.0 request to the MCP server (without initialization check).

        Handles both JSON and SSE (Server-Sent Events) response formats.

        Args:
            method: The RPC method name
            params: Optional parameters

        Returns:
            The result from the JSON-RPC response

        Raises:
            RuntimeError: If the server returns an error or non-200 status
        """
        headers = self._get_headers()
        payload = self._make_jsonrpc_request(method, params)

        logger.debug(f"MCP request to {self.server_url}: method={method}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.server_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(
                        f"MCP server returned {resp.status}: {error_text}"
                    )

                # Handle SSE or JSON response based on content type
                content_type = resp.headers.get("Content-Type", "")
                if "text/event-stream" in content_type:
                    return await self._parse_sse_response(resp)

                data = await resp.json()

                # Check for JSON-RPC error response
                if "error" in data:
                    error = data["error"]
                    error_msg = error.get("message", str(error))
                    error_code = error.get("code", "unknown")
                    raise RuntimeError(f"MCP error ({error_code}): {error_msg}")

                # Return the result
                return data.get("result", data)

    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a JSON-RPC 2.0 request, ensuring session is initialized first.

        Args:
            method: The RPC method name
            params: Optional parameters

        Returns:
            The result from the JSON-RPC response
        """
        await self._ensure_initialized()
        return await self._send_request_raw(method, params)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get tools from MCP server and normalize to OpenAI format.

        Uses JSON-RPC method "tools/list" to fetch available tools.

        MCP returns: {tools: [{name, description, inputSchema}, ...]}
        This returns: [{type: "function", function: {name, description, parameters}}, ...]

        Returns:
            List of tools in OpenAI function calling format

        Raises:
            RuntimeError: If MCP server returns an error
        """
        result = await self._send_request("tools/list")

        # Handle both direct list and {tools: [...]} formats
        if isinstance(result, dict):
            mcp_tools = result.get("tools", [])
        elif isinstance(result, list):
            mcp_tools = result
        else:
            mcp_tools = []

        logger.debug(f"MCP server returned {len(mcp_tools)} tools")

        # Normalize MCP format to OpenAI format
        return [self._normalize_mcp_tool(tool) for tool in mcp_tools]

    def _normalize_mcp_tool(self, mcp_tool: Dict[str, Any]) -> Dict[str, Any]:
        """Convert MCP tool format to OpenAI function calling format.

        MCP format:
            {
                "name": "get_order",
                "description": "Fetch order details",
                "inputSchema": {"type": "object", "properties": {...}}
            }

        OpenAI format:
            {
                "type": "function",
                "function": {
                    "name": "get_order",
                    "description": "Fetch order details",
                    "parameters": {"type": "object", "properties": {...}}
                }
            }

        Args:
            mcp_tool: Tool in MCP format

        Returns:
            Tool in OpenAI function calling format
        """
        return {
            "type": "function",
            "function": {
                "name": mcp_tool.get("name", ""),
                "description": mcp_tool.get("description", ""),
                "parameters": mcp_tool.get("inputSchema", {
                    "type": "object",
                    "properties": {},
                    "required": []
                })
            }
        }

    async def call_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on MCP server using JSON-RPC.

        Uses JSON-RPC method "tools/call" to execute a tool.

        Args:
            name: Tool name (without server prefix)
            arguments: Tool arguments as dict

        Returns:
            Dict with output, error_message, and status fields
        """
        try:
            result = await self._send_request("tools/call", {
                "name": name,
                "arguments": arguments
            })

            # Handle common MCP server errors with user-friendly messages
            if isinstance(result, dict) and result.get("isError"):
                error_content = result.get("content", [])
                if isinstance(error_content, list):
                    for item in error_content:
                        if isinstance(item, dict) and "text" in item:
                            error_text = item.get("text", "")
                            # Provide helpful context for common errors
                            if "Chunk too big" in error_text or "too large" in error_text.lower():
                                return {
                                    "output": None,
                                    "error_message": f"The requested content is too large for the MCP server to return. Try requesting a smaller portion or specific sections. Original error: {error_text}",
                                    "status": "failed"
                                }
                            return {
                                "output": None,
                                "error_message": error_text,
                                "status": "failed"
                            }

            # Handle MCP tool call response formats
            # MCP spec: result contains "content" array with text/image/resource items
            if isinstance(result, dict):
                # Check for content array (MCP spec format)
                if "content" in result:
                    content = result["content"]
                    # Extract text content
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            elif "text" in item:
                                text_parts.append(item["text"])
                    output = "\n".join(text_parts) if text_parts else result
                    return {
                        "output": output,
                        "error_message": None,
                        "status": "completed"
                    }

                # Check for isError flag (MCP spec)
                if result.get("isError"):
                    return {
                        "output": None,
                        "error_message": str(result.get("content", result)),
                        "status": "failed"
                    }

                # If already in expected format, use as-is
                if "status" in result:
                    return result

                # If has result/error fields, normalize
                if "result" in result or "error" in result:
                    return {
                        "output": result.get("result"),
                        "error_message": result.get("error"),
                        "status": "completed" if "result" in result else "failed"
                    }

            # Default: treat entire response as output
            return {
                "output": result,
                "error_message": None,
                "status": "completed"
            }

        except RuntimeError as e:
            error_str = str(e)
            # Provide helpful context for common MCP server errors
            if "Chunk too big" in error_str or "too large" in error_str.lower():
                error_str = f"The requested content is too large for the MCP server. Try requesting specific sections or a smaller scope. Original error: {error_str}"
            return {
                "output": None,
                "error_message": error_str,
                "status": "failed"
            }
