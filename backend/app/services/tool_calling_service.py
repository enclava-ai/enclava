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


class ToolCallingService:
    """Service for LLM tool calling integration"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.tool_mgmt = ToolManagementService(db)
        self.tool_exec = ToolExecutionService(db)

    def _get_user_id(self, user: Union[User, Dict[str, Any]]) -> int:
        """Extract integer user ID from either User model or auth dict."""
        if isinstance(user, dict):
            return int(user.get("id"))
        return int(user.id)

    async def create_chat_completion_with_tools(
        self,
        request: ChatRequest,
        user: Union[User, Dict[str, Any]],
        auto_execute_tools: bool = True,
        max_tool_calls: int = 5,
    ) -> ChatResponse:
        """
        Create chat completion with tool calling support

        Args:
            request: Chat completion request
            user: User making the request
            auto_execute_tools: Whether to automatically execute tool calls
            max_tool_calls: Maximum number of tool calls to prevent infinite loops
        """

        # Get available tools for the user
        available_tools = await self._get_available_tools_for_user(user)

        # Convert tools to OpenAI function format
        if available_tools and not request.tools:
            request.tools = await self._convert_tools_to_openai_format(available_tools)

        messages = request.messages.copy()
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
        self, user: Union[User, Dict[str, Any]]
    ) -> List[Any]:
        """Get tools available to the user"""

        user_id = self._get_user_id(user)

        # Get user's own tools + public approved tools
        tools = await self.tool_mgmt.get_tools(
            user_id=user_id, limit=100  # Reasonable limit for tool calling
        )

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

    async def _execute_tool_call(
        self, tool_call: ToolCall, user: Union[User, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute a single tool call"""

        function_name = tool_call.function.get("name")
        if not function_name:
            raise ValueError("Tool call missing function name")

        # Parse arguments
        try:
            arguments = json.loads(tool_call.function.get("arguments", "{}"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid tool call arguments: {e}")

        # Execute the tool
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
        """Validate which tools are available to the user"""

        availability: Dict[str, bool] = {}

        user_id = self._get_user_id(user)

        for tool_name in tool_names:
            try:
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
            except Exception:
                availability[tool_name] = False

        return availability
