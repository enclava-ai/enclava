"""
Tool Calling Service
Integrates LLM service with tool execution for function calling capabilities
"""
import json
import logging
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.service import llm_service
from app.services.llm.models import ChatRequest, ChatResponse, ChatMessage, ToolCall
from app.services.tool_management_service import ToolManagementService
from app.services.tool_execution_service import ToolExecutionService
from app.models.user import User

logger = logging.getLogger(__name__)

# Tool usage preamble to help LLM choose the right tools
TOOL_USAGE_PREAMBLE = """## Tool Usage Guidelines

You have access to tools. Choose the most appropriate tool based on the user's request.

### Tool Selection Principles:
1. **MCP Tools First**: Use MCP tools (names containing a dot like "deepwiki.read_wiki_structure") for their specific domains. These are specialized tools for specific data sources.
2. **rag_search**: ONLY use for internal/uploaded documents and knowledge bases. Do NOT use for external websites, GitHub repos, or public information.
3. **web_search**: Use for general internet queries when no specialized MCP tool exists for that data source.
4. **User Intent**: If the user explicitly mentions a tool or data source, prioritize that tool.

### Error Handling:
- If a tool returns "too large" or "chunk too big", request smaller/more specific portions instead of retrying the same query.
- If a tool fails repeatedly, explain the limitation and suggest alternatives.
- Do not keep retrying the same failed approach.
"""


class ToolCallingService:
    """Service for LLM tool calling integration"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.tool_mgmt = ToolManagementService(db)
        self.tool_exec = ToolExecutionService(db)
        self._tool_resources: Optional[Dict[str, Any]] = None

    def _get_user_id(self, user: Union[User, Dict[str, Any]]) -> int:
        """Extract integer user ID from either User model or auth dict."""
        if isinstance(user, dict):
            return int(user.get("id"))
        return int(user.id)

    def _generate_tool_preamble(self, tools: List[Dict[str, Any]]) -> str:
        """Generate a tool usage preamble with available tools summary.

        Args:
            tools: List of tools in OpenAI format

        Returns:
            Formatted preamble string with tool summary
        """
        if not tools:
            return ""

        # Categorize tools for the summary
        mcp_tools = []
        builtin_tools = []

        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", "")
            desc = func.get("description", "")[:100]  # Truncate long descriptions

            if "." in name:
                # MCP tool (format: server_name.tool_name)
                mcp_tools.append(f"- {name}: {desc}")
            else:
                builtin_tools.append(f"- {name}: {desc}")

        # Build tool summary
        summary_parts = []
        if mcp_tools:
            summary_parts.append("**Specialized MCP Tools (use these first for their domains):**\n" + "\n".join(mcp_tools))
        if builtin_tools:
            summary_parts.append("**Built-in Tools:**\n" + "\n".join(builtin_tools))

        tool_summary = "\n\n".join(summary_parts)

        return TOOL_USAGE_PREAMBLE + f"\n### Available Tools:\n{tool_summary}"

    async def create_chat_completion_with_tools(
        self,
        request: ChatRequest,
        user: Union[User, Dict[str, Any]],
        auto_execute_tools: bool = True,
        max_tool_calls: int = 5,
        tool_resources: Optional[Dict[str, Any]] = None,
    ) -> ChatResponse:
        """
        Create chat completion with tool calling support

        Args:
            request: Chat completion request
            user: User making the request
            auto_execute_tools: Whether to automatically execute tool calls
            max_tool_calls: Maximum number of tool calls to prevent infinite loops
            tool_resources: Tool resources (e.g., file_search.vector_store_ids for RAG)
        """
        # Store tool_resources for use in _execute_tool_call
        self._tool_resources = tool_resources

        # Get available tools for the user
        available_tools = await self._get_available_tools_for_user(user)

        # Convert tools to OpenAI function format
        if available_tools and not request.tools:
            request.tools = await self._convert_tools_to_openai_format(available_tools)

        messages = request.messages.copy()

        # Inject tool usage preamble if tools are available
        if request.tools:
            preamble = self._generate_tool_preamble(request.tools)
            if preamble:
                # Insert preamble as the first system message (after any existing system message)
                preamble_message = ChatMessage(role="system", content=preamble)
                # Find insertion point - after first system message if exists
                insert_idx = 0
                if messages and messages[0].role == "system":
                    insert_idx = 1
                messages.insert(insert_idx, preamble_message)
                # Update request with preamble-augmented messages
                request.messages = messages

        tool_call_count = 0

        while tool_call_count < max_tool_calls:
            # Make LLM request
            llm_response = await llm_service.create_chat_completion(request)

            # Check if the response contains tool calls
            assistant_message = llm_response.choices[0].message

            if not assistant_message.tool_calls or not auto_execute_tools:
                # No tool calls or auto-execution disabled, return response
                return llm_response

            # Add assistant message with tool calls to conversation
            messages.append(assistant_message)

            # Execute tool calls
            for tool_call in assistant_message.tool_calls:
                try:
                    tool_result = await self._execute_tool_call(tool_call, user)

                    # Add tool result to conversation
                    tool_message = ChatMessage(
                        role="tool",
                        content=json.dumps(tool_result),
                        tool_call_id=tool_call.id,
                    )
                    messages.append(tool_message)

                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    # Add error message to conversation
                    error_message = ChatMessage(
                        role="tool",
                        content=json.dumps({"error": str(e)}),
                        tool_call_id=tool_call.id,
                    )
                    messages.append(error_message)

            # Update request with new messages for next iteration
            request.messages = messages
            tool_call_count += 1

        # If we reach max tool calls, make final request without tools
        request.tools = None
        request.tool_choice = None
        final_response = await llm_service.create_chat_completion(request)

        return final_response

    async def create_chat_completion_stream_with_tools(
        self, request: ChatRequest, user: Union[User, Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Create streaming chat completion with tool calling support
        Note: Tool execution is not auto-executed in streaming mode
        """
        # Get available tools for the user
        available_tools = await self._get_available_tools_for_user(user)

        # Convert tools to OpenAI function format
        if available_tools and not request.tools:
            request.tools = await self._convert_tools_to_openai_format(available_tools)

        # Stream the response
        async for chunk in llm_service.create_chat_completion_stream(request):
            yield chunk

    async def execute_tool_by_name(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user: Union[User, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute a tool by name directly"""

        user_id = self._get_user_id(user)

        # Find the tool
        tool = await self.tool_mgmt.get_tool_by_name_and_user(tool_name, user_id)
        if not tool:
            # Try to find public approved tool
            tools = await self.tool_mgmt.get_tools(
                user_id=user_id,
                search=tool_name,
                is_public=True,
                is_approved=True,
                limit=1,
            )
            if not tools:
                raise ValueError(f"Tool '{tool_name}' not found or not accessible")
            tool = tools[0]

        # Execute the tool
        execution = await self.tool_exec.execute_tool(
            tool_id=tool.id, user_id=user_id, parameters=parameters
        )

        # Return execution result
        return {
            "execution_id": execution.id,
            "status": execution.status,
            "output": execution.output,
            "error_message": execution.error_message,
            "execution_time_ms": execution.execution_time_ms,
        }

    async def _get_available_tools_for_user(
        self, user: Union[User, Dict[str, Any]], include_builtin: bool = True
    ) -> List[Any]:
        """Get tools available to the user.

        Returns Tool model objects AND BuiltinTool instances (NOT OpenAI schemas).
        Conversion to OpenAI format happens in _convert_tools_to_openai_format.

        Args:
            user: User requesting tools
            include_builtin: Whether to include built-in tools (default: True)

        Returns:
            List of tool objects (mix of Tool models and BuiltinTool instances)
        """
        from app.services.builtin_tools.registry import BuiltinToolRegistry

        tools = []
        user_id = self._get_user_id(user)

        # Add built-in tools (as BuiltinTool objects, NOT schemas)
        if include_builtin:
            builtin_tools = BuiltinToolRegistry.get_all()
            tools.extend(builtin_tools)

        # Add custom tools (as Tool model objects)
        custom_tools = await self.tool_mgmt.get_tools(
            user_id=user_id, limit=100  # Reasonable limit for tool calling
        )
        tools.extend(custom_tools)

        return tools

    async def _convert_tools_to_openai_format(
        self, tools: List[Any]
    ) -> List[Dict[str, Any]]:
        """Convert internal tool format to OpenAI function calling format"""

        openai_tools = []

        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or f"Execute {tool.display_name}",
                    "parameters": tool.parameters_schema
                    or {"type": "object", "properties": {}, "required": []},
                },
            }
            openai_tools.append(openai_tool)

        return openai_tools

    async def _get_mcp_config(
        self,
        server_name: str,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get MCP server configuration by name from database.

        Looks up MCP server from database. Users can access their own
        servers and global servers.

        Args:
            server_name: Name of the MCP server (e.g., "order-api")
            user_id: User ID for access control

        Returns:
            Dict with url, api_key (decrypted), timeout, max_retries,
            or None if not configured
        """
        from app.services.mcp_server_service import MCPServerService

        service = MCPServerService(self.db)
        return await service.get_server_config_for_tool_calling(server_name, user_id)

    async def _execute_tool_call(
        self, tool_call: ToolCall, user: Union[User, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute a single tool call - routes to builtin, MCP, or custom tools.

        Routing priority:
        1. Built-in tools (rag_search, web_search)
        2. MCP tools (server_name.tool_name format)
        3. Custom user tools (from database)

        Args:
            tool_call: ToolCall object with function name and arguments
            user: User executing the tool

        Returns:
            Dict with execution results (output, error_message, status)
        """
        from app.services.builtin_tools.registry import BuiltinToolRegistry
        from app.services.builtin_tools.base import ToolExecutionContext

        function_name = tool_call.function.get("name")
        if not function_name:
            raise ValueError("Tool call missing function name")

        # Parse arguments
        try:
            arguments = json.loads(tool_call.function.get("arguments", "{}"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid tool call arguments: {e}")

        # 1. Check built-in tools first
        if BuiltinToolRegistry.is_builtin(function_name):
            tool = BuiltinToolRegistry.get(function_name)
            ctx = ToolExecutionContext(
                user_id=self._get_user_id(user),
                db=self.db,
                tool_resources=self._tool_resources
            )
            result = await tool.execute(arguments, ctx)
            return {
                "output": result.output,
                "error_message": result.error,
                "status": "completed" if result.success else "failed"
            }

        # 2. Check MCP tools (format: "server_name.tool_name")
        if "." in function_name:
            server_name, tool_name = function_name.split(".", 1)
            user_id = self._get_user_id(user)
            mcp_config = await self._get_mcp_config(server_name, user_id)
            if mcp_config:
                from app.services.mcp_client import MCPClient
                client = MCPClient(
                    server_url=mcp_config["url"],
                    api_key=mcp_config.get("api_key"),
                    api_key_header_name=mcp_config.get("api_key_header_name", "Authorization"),
                    timeout_seconds=mcp_config.get("timeout", 30),
                    max_retries=mcp_config.get("max_retries", 3)
                )
                return await client.call_tool(tool_name, arguments)

        # 3. Fallback to custom tools (existing behavior)
        result = await self.execute_tool_by_name(function_name, arguments, user)

        return result

    async def get_tool_call_history(
        self, user: Union[User, Dict[str, Any]], limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent tool execution history for the user"""

        user_id = self._get_user_id(user)

        executions = await self.tool_mgmt.get_tool_executions(
            user_id=user_id, executed_by_user_id=user_id, limit=limit
        )

        history = []
        for execution in executions:
            history.append(
                {
                    "id": execution.id,
                    "tool_name": execution.tool.name if execution.tool else "unknown",
                    "parameters": execution.parameters,
                    "status": execution.status,
                    "output": execution.output,
                    "error_message": execution.error_message,
                    "execution_time_ms": execution.execution_time_ms,
                    "created_at": execution.created_at.isoformat()
                    if execution.created_at
                    else None,
                    "completed_at": execution.completed_at.isoformat()
                    if execution.completed_at
                    else None,
                }
            )

        return history

    async def validate_tool_availability(
        self, tool_names: List[str], user: Union[User, Dict[str, Any]]
    ) -> Dict[str, bool]:
        """Validate which tools are available to the user.

        Checks tools in this priority order:
        1. Built-in tools (rag_search, web_search)
        2. MCP tools (server_name.tool_name format)
        3. Custom user tools (from database)

        Args:
            tool_names: List of tool names to validate
            user: User requesting validation

        Returns:
            Dict mapping tool names to availability (True/False)
        """
        from app.services.builtin_tools.registry import BuiltinToolRegistry

        availability: Dict[str, bool] = {}
        user_id = self._get_user_id(user)

        for tool_name in tool_names:
            try:
                # 1. Check built-in tools first
                if BuiltinToolRegistry.is_builtin(tool_name):
                    availability[tool_name] = True
                    continue

                # 2. Check MCP tools (format: "server_name.tool_name")
                if "." in tool_name:
                    server_name = tool_name.split(".", 1)[0]
                    mcp_config = await self._get_mcp_config(server_name, user_id)
                    if mcp_config:
                        # MCP server is configured, assume tool is available
                        # (we don't check actual tool existence to avoid overhead)
                        availability[tool_name] = True
                        continue

                # 3. Check custom user tools (from database)
                tool = await self.tool_mgmt.get_tool_by_name_and_user(tool_name, user_id)
                if tool:
                    availability[tool_name] = tool.can_be_used_by(user)
                else:
                    # Check public tools
                    tools = await self.tool_mgmt.get_tools(
                        user_id=user_id,
                        search=tool_name,
                        is_public=True,
                        is_approved=True,
                        limit=1,
                    )
                    availability[tool_name] = len(tools) > 0
            except Exception as e:
                logger.error(f"Error validating tool '{tool_name}': {e}")
                availability[tool_name] = False

        return availability
