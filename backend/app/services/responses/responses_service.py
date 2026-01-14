"""
ResponsesService - Core service for Responses API

Orchestrates agentic interactions with automatic tool execution,
budget enforcement, and state management.
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.response import Response
from app.models.conversation import Conversation
from app.models.agent_config import AgentConfig
from app.schemas.responses import ResponseCreateRequest, ResponseObject, TokenUsage
from app.services.responses.translator import ItemMessageTranslator
from app.services.tool_calling_service import ToolCallingService
from app.services.llm.models import ChatRequest, ChatMessage
from app.services.budget_enforcement import BudgetEnforcementService

logger = logging.getLogger(__name__)


class ResponsesService:
    """Service for creating and managing responses with tool execution"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.translator = ItemMessageTranslator()
        self.tool_calling_service = ToolCallingService(db)
        self.budget_service = BudgetEnforcementService(db)

    async def create_response(
        self,
        request: ResponseCreateRequest,
        api_key_context: Dict[str, Any]
    ) -> ResponseObject:
        """Create a response with automatic tool execution.

        Flow:
        1. Load agent config if prompt referenced
        2. Load previous context if chained
        3. Budget check
        4. Execute agentic loop with tools
        5. Store response if store=True
        6. Record usage
        7. Return response object

        Args:
            request: Response creation request
            api_key_context: API key authentication context

        Returns:
            ResponseObject with output items and usage
        """
        start_time = time.time()
        response_id = self._generate_response_id()
        api_key = api_key_context.get("api_key")
        user = api_key_context.get("user")

        try:
            # 1. Load agent config (prompt) if referenced
            agent_config = None
            if request.prompt:
                agent_config = await self._load_agent_config(request.prompt.id, user.id)
                if agent_config:
                    # Merge agent config with request
                    request = self._merge_agent_config(request, agent_config)

            # 2. Normalize input to items format
            input_items = self.translator.normalize_input(request.input)

            # 3. Load previous response context if chained
            if request.previous_response_id:
                previous_items = await self._load_previous_response(
                    request.previous_response_id,
                    user.id
                )
                if previous_items:
                    input_items = previous_items + input_items

            # 4. Load conversation context if specified
            if request.conversation:
                conv_items = await self._load_conversation(request.conversation, user.id)
                if conv_items:
                    input_items = conv_items + input_items

            # 5. Estimate tokens for budget check
            estimated_tokens = self._estimate_tokens(input_items, request.instructions)

            # 6. Budget check and reserve
            (
                is_allowed,
                error_msg,
                warnings,
                reserved_budget_ids
            ) = self.budget_service.atomic_check_and_reserve_budget(
                api_key,
                request.model,
                estimated_tokens
            )

            if not is_allowed:
                return self._create_error_response(
                    response_id,
                    request.model,
                    "budget_exceeded",
                    error_msg
                )

            # 7. Convert items to messages for LLM
            messages = self.translator.items_to_messages(input_items)

            # 8. Add instructions as system message if provided
            if request.instructions:
                messages.insert(0, ChatMessage(role="system", content=request.instructions))

            # 9. Prepare chat request
            chat_request = ChatRequest(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                tools=None,  # Will be set by tool calling service
                stream=False
            )

            # 10. Execute agentic loop with tool calling
            total_input_tokens = 0
            total_output_tokens = 0

            llm_response = await self.tool_calling_service.create_chat_completion_with_tools(
                chat_request,
                user,
                auto_execute_tools=True,
                max_tool_calls=5
            )

            # 11. Extract usage from LLM response
            if llm_response.usage:
                total_input_tokens = llm_response.usage.prompt_tokens
                total_output_tokens = llm_response.usage.completion_tokens

            # 12. Convert messages to output items
            assistant_message = llm_response.choices[0].message
            output_items = self.translator.messages_to_output_items([assistant_message])

            # 13. Finalize budget with actual usage
            if reserved_budget_ids:
                self.budget_service.atomic_finalize_usage(
                    reserved_budget_ids,
                    api_key,
                    request.model,
                    total_input_tokens,
                    total_output_tokens
                )

            # 14. Create response object
            response_obj = ResponseObject(
                id=response_id,
                object="response",
                created_at=int(time.time()),
                model=request.model,
                output=output_items,
                output_text=self.translator.extract_text_from_output_items(output_items),
                status="completed",
                usage=TokenUsage(
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    total_tokens=total_input_tokens + total_output_tokens
                ),
                conversation={"id": request.conversation} if request.conversation else None,
                previous_response_id=request.previous_response_id,
                metadata=request.metadata
            )

            # 15. Store response if requested
            if request.store:
                await self._store_response(
                    response_obj,
                    input_items,
                    user.id,
                    api_key.id
                )

            # 16. Update conversation if specified
            if request.conversation:
                await self._update_conversation(
                    request.conversation,
                    input_items + output_items,
                    user.id
                )

            execution_time = (time.time() - start_time) * 1000
            logger.info(
                f"Response {response_id} created successfully in {execution_time:.2f}ms, "
                f"tokens: {total_input_tokens + total_output_tokens}"
            )

            return response_obj

        except Exception as e:
            logger.error(f"Error creating response: {e}", exc_info=True)
            return self._create_error_response(
                response_id,
                request.model,
                "internal_error",
                str(e)
            )

    async def get_response(
        self,
        response_id: str,
        user_id: int
    ) -> Optional[ResponseObject]:
        """Get a stored response by ID.

        Args:
            response_id: Response ID
            user_id: User ID for ownership check

        Returns:
            ResponseObject if found, None otherwise
        """
        try:
            stmt = select(Response).where(
                Response.id == response_id,
                Response.user_id == user_id
            )
            result = await self.db.execute(stmt)
            response = result.scalar_one_or_none()

            if not response:
                return None

            # Convert to ResponseObject
            return ResponseObject(**response.to_dict())

        except Exception as e:
            logger.error(f"Error retrieving response {response_id}: {e}")
            return None

    async def _load_agent_config(
        self,
        config_id: str,
        user_id: int
    ) -> Optional[AgentConfig]:
        """Load agent configuration by ID or name.

        Args:
            config_id: Agent config ID (integer) or name (string)
            user_id: User ID for access control

        Returns:
            AgentConfig if found and accessible
        """
        try:
            # Build access control condition
            access_condition = (
                (AgentConfig.created_by_user_id == user_id) |
                (AgentConfig.is_public == True)
            )

            # Try by name first
            stmt = select(AgentConfig).where(
                AgentConfig.name == config_id,
                AgentConfig.is_active == True,
                access_condition
            )
            result = await self.db.execute(stmt)
            agent_config = result.scalar_one_or_none()

            # If not found by name, try by ID
            if not agent_config:
                try:
                    config_id_int = int(config_id)
                    stmt = select(AgentConfig).where(
                        AgentConfig.id == config_id_int,
                        AgentConfig.is_active == True,
                        access_condition
                    )
                    result = await self.db.execute(stmt)
                    agent_config = result.scalar_one_or_none()
                except (ValueError, TypeError):
                    # config_id is not a valid integer, skip ID lookup
                    pass

            if agent_config:
                logger.info(f"Loaded agent config: {agent_config.name}")

            return agent_config

        except Exception as e:
            logger.error(f"Error loading agent config {config_id}: {e}")
            return None

    def _merge_agent_config(
        self,
        request: ResponseCreateRequest,
        agent_config: AgentConfig
    ) -> ResponseCreateRequest:
        """Merge agent config into request.

        Agent config provides defaults that can be overridden by request.

        Args:
            request: Original request
            agent_config: Agent configuration

        Returns:
            Merged request
        """
        # Use agent's instructions if not provided in request
        if not request.instructions and agent_config.system_prompt:
            request.instructions = agent_config.system_prompt

        # Use agent's model if not specified
        if not request.model:
            request.model = agent_config.model

        # Use agent's temperature if not specified
        if request.temperature is None:
            request.temperature = agent_config.temperature

        # Use agent's max_tokens if not specified
        if request.max_tokens is None:
            request.max_tokens = agent_config.max_tokens

        # Merge tools from agent config
        if agent_config.tools_config:
            config_tools = self._extract_tools_from_config(agent_config.tools_config)
            if config_tools:
                if request.tools:
                    # Combine tools (request tools take precedence)
                    request.tools = request.tools + config_tools
                else:
                    request.tools = config_tools

        return request

    def _extract_tools_from_config(self, tools_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tool definitions from agent config.

        Args:
            tools_config: Tools configuration from agent

        Returns:
            List of tool definitions
        """
        tools = []

        # Built-in tools
        builtin_tools = tools_config.get("builtin_tools", [])
        for tool_name in builtin_tools:
            if tool_name == "rag_search":
                tools.append({"type": "file_search"})
            elif tool_name == "web_search":
                tools.append({"type": "web_search"})

        # MCP servers
        mcp_servers = tools_config.get("mcp_servers", [])
        for server_name in mcp_servers:
            tools.append({"type": "mcp", "server": server_name})

        return tools

    async def _load_previous_response(
        self,
        response_id: str,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """Load items from previous response for chaining.

        Args:
            response_id: Previous response ID
            user_id: User ID for ownership check

        Returns:
            Combined input and output items from previous response
        """
        try:
            stmt = select(Response).where(
                Response.id == response_id,
                Response.user_id == user_id
            )
            result = await self.db.execute(stmt)
            response = result.scalar_one_or_none()

            if not response:
                logger.warning(f"Previous response {response_id} not found")
                return []

            # Return input + output items for context
            items = []
            if response.input_items:
                items.extend(response.input_items)
            if response.output_items:
                items.extend(response.output_items)

            return items

        except Exception as e:
            logger.error(f"Error loading previous response {response_id}: {e}")
            return []

    async def _load_conversation(
        self,
        conversation_id: str,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """Load items from conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID for ownership check

        Returns:
            All items from conversation
        """
        try:
            stmt = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            )
            result = await self.db.execute(stmt)
            conversation = result.scalar_one_or_none()

            if not conversation:
                logger.warning(f"Conversation {conversation_id} not found")
                return []

            return conversation.items or []

        except Exception as e:
            logger.error(f"Error loading conversation {conversation_id}: {e}")
            return []

    async def _store_response(
        self,
        response_obj: ResponseObject,
        input_items: List[Dict[str, Any]],
        user_id: int,
        api_key_id: int
    ):
        """Store response in database.

        Args:
            response_obj: Response object to store
            input_items: Input items
            user_id: User ID
            api_key_id: API key ID
        """
        try:
            # Calculate TTL
            expires_at = datetime.utcnow() + Response.get_default_ttl()

            response = Response(
                id=response_obj.id,
                object=response_obj.object,
                user_id=user_id,
                api_key_id=api_key_id,
                model=response_obj.model,
                instructions=None,  # Not stored to save space
                input_items=input_items,
                output_items=response_obj.output,
                status=response_obj.status,
                error=response_obj.error,
                previous_response_id=response_obj.previous_response_id,
                conversation_id=response_obj.conversation.get("id") if response_obj.conversation else None,
                input_tokens=response_obj.usage.input_tokens,
                output_tokens=response_obj.usage.output_tokens,
                total_tokens=response_obj.usage.total_tokens,
                store=True,
                response_metadata=response_obj.metadata,
                created_at=datetime.utcnow(),
                expires_at=expires_at
            )

            self.db.add(response)
            await self.db.commit()

            logger.debug(f"Stored response {response_obj.id}")

        except Exception as e:
            logger.error(f"Error storing response: {e}")
            await self.db.rollback()

    async def _update_conversation(
        self,
        conversation_id: str,
        new_items: List[Dict[str, Any]],
        user_id: int
    ):
        """Update conversation with new items.

        Args:
            conversation_id: Conversation ID
            new_items: New items to add
            user_id: User ID for ownership check
        """
        try:
            stmt = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            )
            result = await self.db.execute(stmt)
            conversation = result.scalar_one_or_none()

            if conversation:
                conversation.add_items(new_items)
                await self.db.commit()
                logger.debug(f"Updated conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Error updating conversation {conversation_id}: {e}")
            await self.db.rollback()

    def _estimate_tokens(
        self,
        items: List[Dict[str, Any]],
        instructions: Optional[str]
    ) -> int:
        """Estimate token count for budget check.

        Rough estimation: ~4 characters per token

        Args:
            items: Input items
            instructions: System instructions

        Returns:
            Estimated token count
        """
        total_chars = 0

        # Count instructions
        if instructions:
            total_chars += len(instructions)

        # Count items
        for item in items:
            total_chars += len(json.dumps(item))

        # Convert to tokens (rough estimate)
        return total_chars // 4

    def _generate_response_id(self) -> str:
        """Generate unique response ID.

        Returns:
            Response ID in format: resp_<timestamp>_<random>
        """
        import secrets
        timestamp = int(time.time() * 1000)
        random_suffix = secrets.token_hex(4)
        return f"resp_{timestamp}_{random_suffix}"

    def _create_error_response(
        self,
        response_id: str,
        model: str,
        error_type: str,
        error_message: str
    ) -> ResponseObject:
        """Create error response object.

        Args:
            response_id: Response ID
            model: Model name
            error_type: Error type code
            error_message: Error description

        Returns:
            ResponseObject with error status
        """
        return ResponseObject(
            id=response_id,
            object="response",
            created_at=int(time.time()),
            model=model,
            output=[],
            output_text=None,
            status="failed",
            error={
                "type": error_type,
                "code": error_type,
                "message": error_message
            },
            usage=TokenUsage(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0
            )
        )

    async def create_response_stream(
        self,
        request: ResponseCreateRequest,
        api_key_context: Dict[str, Any]
    ):
        """Create streaming response with automatic tool execution.

        Streams events as response is being generated. Tool calls are executed
        and their results streamed back before continuing with LLM response.

        Args:
            request: Response creation request
            api_key_context: API key authentication context

        Yields:
            SSE formatted event strings
        """
        from app.services.responses.streaming import (
            stream_response_events_with_tools,
            ResponseStreamEvent,
            ResponseStreamEventType
        )

        response_id = self._generate_response_id()
        api_key = api_key_context.get("api_key")
        user = api_key_context.get("user")

        try:
            # 1. Load agent config if referenced
            agent_config = None
            tool_resources = None
            if request.prompt:
                agent_config = await self._load_agent_config(request.prompt.id, user.id)
                if agent_config:
                    request = self._merge_agent_config(request, agent_config)
                    # Extract tool_resources for RAG/file_search
                    tool_resources = agent_config.tool_resources

            # 2. Normalize input to items format
            input_items = self.translator.normalize_input(request.input)

            # 3. Load previous context if chained
            if request.previous_response_id:
                previous_items = await self._load_previous_response(
                    request.previous_response_id,
                    user.id
                )
                if previous_items:
                    input_items = previous_items + input_items

            # 4. Load conversation context if specified
            if request.conversation:
                conv_items = await self._load_conversation(request.conversation, user.id)
                if conv_items:
                    input_items = conv_items + input_items

            # 5. Estimate tokens for budget check
            estimated_tokens = self._estimate_tokens(input_items, request.instructions)

            # 6. Budget check and reserve
            (
                is_allowed,
                error_msg,
                warnings,
                reserved_budget_ids
            ) = self.budget_service.atomic_check_and_reserve_budget(
                api_key,
                request.model,
                estimated_tokens
            )

            if not is_allowed:
                error_event = ResponseStreamEvent(
                    ResponseStreamEventType.FAILED,
                    {
                        "id": response_id,
                        "object": "response",
                        "status": "failed",
                        "error": {
                            "type": "budget_exceeded",
                            "code": "budget_exceeded",
                            "message": error_msg
                        }
                    }
                )
                yield error_event.to_sse()
                return

            # 7. Convert items to messages for LLM
            messages = self.translator.items_to_messages(input_items)

            # 8. Add instructions as system message if provided
            if request.instructions:
                messages.insert(0, ChatMessage(role="system", content=request.instructions))

            # 9. Prepare chat request for streaming with tools
            chat_request = ChatRequest(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                tools=None,  # Will be set by tool calling service
                stream=True  # Enable streaming
            )

            # 10. Stream response with tool execution support
            # This routes through the tool calling service to include tool definitions
            # and handles tool execution when tool calls are detected
            async for event in stream_response_events_with_tools(
                response_id=response_id,
                model=request.model,
                chat_request=chat_request,
                tool_calling_service=self.tool_calling_service,
                user=user,
                tool_resources=tool_resources,
                max_tool_calls=5
            ):
                yield event

        except Exception as e:
            logger.error(f"Error in streaming response: {e}", exc_info=True)

            error_event = ResponseStreamEvent(
                ResponseStreamEventType.FAILED,
                {
                    "id": response_id,
                    "object": "response",
                    "status": "failed",
                    "error": {
                        "type": "internal_error",
                        "code": "internal_error",
                        "message": str(e)
                    }
                }
            )
            yield error_event.to_sse()
