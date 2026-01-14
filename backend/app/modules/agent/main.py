"""
Agent Module Implementation

Provides pre-configured AI agents with custom tool sets and prompts.
"""

import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.logging import get_logger
from app.services.llm.service import llm_service
from app.services.llm.models import ChatRequest, ChatMessage
from app.services.base_module import BaseModule, Permission
from app.models.user import User
from app.models.agent_config import AgentConfig
from app.models.agent_conversation import AgentConversation, AgentMessage
from app.core.security import get_current_user
from app.db.database import get_db
from app.services.api_key_auth import get_api_key_context, get_api_key_auth
from app.models.api_key import APIKey

# Import protocols for type hints and dependency injection
from ..protocols import RAGServiceProtocol

logger = get_logger(__name__)


def _get_user_id(user: Union[User, Dict[str, Any]]) -> int:
    """Extract integer user ID from either User model or auth dict.

    Consistent helper function for user ID extraction across the module.
    """
    if isinstance(user, dict):
        return int(user.get("id"))
    return int(user.id)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class AgentConfigCreate(BaseModel):
    """Schema for creating an agent config."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    system_prompt: str = Field(..., min_length=1)
    model: str = Field(default="gpt-oss-120b")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=1, le=32000)
    builtin_tools: List[str] = Field(default_factory=list)
    mcp_servers: List[str] = Field(default_factory=list)
    include_custom_tools: bool = Field(default=True)
    tool_choice: str = Field(default="auto")
    max_iterations: int = Field(default=5, ge=1, le=10)
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_public: bool = Field(default=False)
    tool_resources: Optional[Dict[str, Any]] = Field(default=None)


class AgentConfigUpdate(BaseModel):
    """Schema for updating an agent config."""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    builtin_tools: Optional[List[str]] = None
    mcp_servers: Optional[List[str]] = None
    include_custom_tools: Optional[bool] = None
    tool_choice: Optional[str] = None
    max_iterations: Optional[int] = Field(None, ge=1, le=10)
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    tool_resources: Optional[Dict[str, Any]] = None


# Legacy request/response models (for internal process_request compatibility)
class AgentChatRequest(BaseModel):
    """Request to chat with an agent (legacy format)."""
    agent_config_id: int
    message: str
    conversation_id: Optional[str] = None


class AgentChatResponse(BaseModel):
    """Response from chatting with an agent (legacy format)."""
    content: Optional[str]
    conversation_id: str
    tool_calls_made: List[Dict[str, Any]] = Field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None


# OpenAI-compatible models
class ToolCall(BaseModel):
    """OpenAI-compatible tool call."""
    id: str = Field(..., description="Tool call identifier")
    type: str = Field(default="function", description="Tool call type")
    function: Dict[str, Any] = Field(..., description="Function call details")


class ChatMessage(BaseModel):
    """OpenAI-compatible chat message."""
    role: str = Field(..., description="Message role (system, user, assistant)")
    content: Optional[str] = Field(None, description="Message content")
    tool_calls: Optional[List[ToolCall]] = Field(None, description="Tool calls made by assistant")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID for tool responses")


class AgentChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request for agents."""
    messages: List[ChatMessage] = Field(..., description="List of messages")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(None, description="Temperature for sampling")
    top_p: Optional[float] = Field(None, description="Top-p sampling parameter")
    frequency_penalty: Optional[float] = Field(None, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(None, description="Presence penalty")
    stop: Optional[List[str]] = Field(None, description="Stop sequences")
    stream: Optional[bool] = Field(False, description="Stream response")


class ChatChoice(BaseModel):
    """OpenAI-compatible chat choice."""
    index: int
    message: ChatMessage
    finish_reason: str


class ChatUsage(BaseModel):
    """OpenAI-compatible usage info."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AgentChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: ChatUsage


# ============================================================================
# Agent Module Implementation
# ============================================================================

class AgentModule(BaseModule):
    """Main agent module implementation"""

    def __init__(self, rag_service: Optional[RAGServiceProtocol] = None):
        super().__init__("agent")
        self.rag_module = rag_service
        self._router: Optional[APIRouter] = None

    @property
    def router(self) -> APIRouter:
        """Router property for module_manager auto-registration."""
        if self._router is None:
            self._router = self.get_router()
        return self._router

    async def initialize(self, **kwargs):
        """Initialize the agent module"""
        await super().initialize(**kwargs)

        # Initialize the LLM service
        await llm_service.initialize()

        # Get RAG module dependency if not already injected
        if not self.rag_module:
            try:
                from app.services.module_manager import module_manager

                if (
                    hasattr(module_manager, "modules")
                    and "rag" in module_manager.modules
                ):
                    self.rag_module = module_manager.modules["rag"]
                    logger.info("RAG module injected from module manager")
            except Exception as e:
                logger.warning(f"Could not inject RAG module: {e}")

        logger.info("Agent module initialized")
        logger.info(f"LLM service available: {llm_service._initialized}")
        logger.info(f"RAG module available: {self.rag_module is not None}")

    async def cleanup(self):
        """Cleanup agent module resources"""
        logger.info("Agent module cleanup completed")

    def get_required_permissions(self) -> List[Permission]:
        """Get required permissions for agent module"""
        return [
            Permission("agents", "create", "Create agent configurations"),
            Permission("agents", "configure", "Configure agent settings"),
            Permission("agents", "chat", "Chat with agents"),
            Permission("agents", "manage", "Manage all agents"),
        ]

    async def process_request(
        self, request_type: str, data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process agent requests"""
        if request_type == "chat":
            # Handle chat requests
            chat_request = AgentChatRequest(**data)
            user_id = context.get("user_id")
            db = context.get("db")

            if db:
                response = await self.chat_with_agent(
                    chat_request, user_id, db, context.get("current_user")
                )
                return {
                    "success": True,
                    "response": response.content,
                    "conversation_id": response.conversation_id,
                    "tool_calls": response.tool_calls_made,
                }

        return {"success": False, "error": f"Unknown request type: {request_type}"}

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def get_agent_config_by_id(
        self,
        config_id: int,
        current_user: Union[User, Dict[str, Any]],
        db: AsyncSession
    ) -> AgentConfig:
        """Load agent config by ID with access control."""
        user_id = _get_user_id(current_user)

        stmt = select(AgentConfig).where(
            AgentConfig.id == config_id,
            or_(
                AgentConfig.created_by_user_id == user_id,
                AgentConfig.is_public == True
            )
        )
        result = await db.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(
                status_code=404,
                detail="Agent config not found or access denied"
            )

        return config

    async def load_conversation_history(
        self,
        conversation_id: str,
        user_id: int,
        db: AsyncSession
    ) -> List[ChatMessage]:
        """Load conversation history from AgentMessage table.

        Security: Verifies the conversation belongs to the user before loading messages.
        """
        # Find conversation with ownership verification
        conv_stmt = select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.user_id == str(user_id)
        )
        conv_result = await db.execute(conv_stmt)
        conversation = conv_result.scalar_one_or_none()

        if not conversation:
            return []

        # Load messages by timestamp
        msg_stmt = select(AgentMessage).where(
            AgentMessage.conversation_id == conversation.id
        ).order_by(AgentMessage.timestamp)
        msg_result = await db.execute(msg_stmt)
        messages = msg_result.scalars().all()

        # Convert to ChatMessage format
        return [
            ChatMessage(
                role=msg.role,
                content=msg.content,
                tool_calls=msg.tool_calls,
                tool_call_id=msg.tool_call_id
            )
            for msg in messages
        ]

    async def get_or_create_conversation(
        self,
        conversation_id: Optional[str],
        agent_config_id: int,
        user_id: int,
        db: AsyncSession
    ) -> AgentConversation:
        """Get existing conversation or create new one.

        Security: When retrieving, verify conversation belongs to user and agent.
        """
        if conversation_id:
            stmt = select(AgentConversation).where(
                AgentConversation.id == conversation_id,
                AgentConversation.user_id == str(user_id),
                AgentConversation.agent_config_id == agent_config_id
            )
            result = await db.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        # Create new conversation
        new_conv = AgentConversation(
            id=str(uuid.uuid4()),
            agent_config_id=agent_config_id,
            user_id=str(user_id),
            title="Agent Chat",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_conv)
        await db.commit()
        await db.refresh(new_conv)
        return new_conv

    async def save_agent_message(
        self,
        conversation_id: str,
        role: str,
        content: Optional[str],
        tool_calls: Optional[List[Dict[str, Any]]],
        db: AsyncSession
    ) -> AgentMessage:
        """Save a message to the conversation."""
        msg = AgentMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            timestamp=datetime.utcnow()
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    # ========================================================================
    # Agent CRUD Operations
    # ========================================================================

    async def create_agent_config(
        self,
        request: AgentConfigCreate,
        user_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Create a new agent configuration."""
        # Build tools_config from individual fields
        tools_config = {
            "builtin_tools": request.builtin_tools,
            "mcp_servers": request.mcp_servers,
            "include_custom_tools": request.include_custom_tools,
            "tool_choice": request.tool_choice,
            "max_iterations": request.max_iterations
        }

        agent = AgentConfig(
            name=request.name,
            description=request.description,
            system_prompt=request.system_prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tools_config=tools_config,
            tool_resources=request.tool_resources,
            category=request.category,
            tags=request.tags,
            is_public=request.is_public,
            is_template=False,
            created_by_user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(agent)
        await db.commit()
        await db.refresh(agent)

        return agent.to_dict()

    async def list_agent_configs(
        self,
        user_id: int,
        category: Optional[str],
        is_public: Optional[bool],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """List agent configurations accessible to the user."""
        # Build query
        stmt = select(AgentConfig).where(
            or_(
                AgentConfig.created_by_user_id == user_id,
                AgentConfig.is_public == True
            )
        )

        if category:
            stmt = stmt.where(AgentConfig.category == category)
        if is_public is not None:
            stmt = stmt.where(AgentConfig.is_public == is_public)

        stmt = stmt.order_by(AgentConfig.created_at.desc())

        result = await db.execute(stmt)
        configs = result.scalars().all()

        return {
            "configs": [cfg.to_dict() for cfg in configs],
            "count": len(configs)
        }

    async def update_agent_config(
        self,
        config_id: int,
        request: AgentConfigUpdate,
        user_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Update an agent configuration."""
        # Get config and verify ownership
        stmt = select(AgentConfig).where(
            AgentConfig.id == config_id,
            AgentConfig.created_by_user_id == user_id
        )
        result = await db.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(
                status_code=404,
                detail="Agent config not found or cannot be modified"
            )

        # Update fields
        update_data = request.dict(exclude_unset=True)

        # Handle tools_config fields
        if any(k in update_data for k in ['builtin_tools', 'mcp_servers', 'include_custom_tools', 'tool_choice', 'max_iterations']):
            tools_config = config.tools_config.copy()
            for key in ['builtin_tools', 'mcp_servers', 'include_custom_tools', 'tool_choice', 'max_iterations']:
                if key in update_data:
                    tools_config[key] = update_data.pop(key)
            config.tools_config = tools_config

        # Update remaining fields
        for key, value in update_data.items():
            setattr(config, key, value)

        config.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(config)

        return config.to_dict()

    async def delete_agent_config(
        self,
        config_id: int,
        user_id: int,
        db: AsyncSession
    ) -> Dict[str, str]:
        """Delete an agent configuration."""
        # Get config and verify ownership
        stmt = select(AgentConfig).where(
            AgentConfig.id == config_id,
            AgentConfig.created_by_user_id == user_id
        )
        result = await db.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(
                status_code=404,
                detail="Agent config not found or cannot be deleted"
            )

        db.delete(config)  # delete() is synchronous in SQLAlchemy
        await db.commit()

        return {"message": "Agent config deleted successfully"}

    # ========================================================================
    # Agent Chat
    # ========================================================================

    async def chat_with_agent(
        self,
        request: AgentChatRequest,
        current_user: Union[User, Dict[str, Any]],
        db: AsyncSession,
        api_key_context: Optional[Dict[str, Any]] = None
    ) -> AgentChatResponse:
        """Chat with a pre-configured agent."""
        user_id = _get_user_id(current_user)

        # Load agent config
        agent = await self.get_agent_config_by_id(request.agent_config_id, current_user, db)

        # Check API key access restrictions if using API key authentication
        if api_key_context:
            api_key = api_key_context.get("api_key")
            if api_key and not api_key.can_access_agent(request.agent_config_id):
                raise HTTPException(
                    status_code=403,
                    detail="API key not authorized to access this agent"
                )

        # Get or create conversation
        conversation = await self.get_or_create_conversation(
            request.conversation_id, agent.id, user_id, db
        )

        # Save user message
        await self.save_agent_message(
            conversation.id,
            "user",
            request.message,
            None,
            db
        )

        # Load conversation history
        history = await self.load_conversation_history(conversation.id, user_id, db)

        # Build messages for LLM
        messages = []
        if agent.system_prompt:
            messages.append(ChatMessage(role="system", content=agent.system_prompt))
        messages.extend(history)

        # Build tools from agent config
        from app.services.builtin_tools.registry import BuiltinToolRegistry
        from app.services.mcp_server_service import MCPServerService
        from app.services.tool_calling_service import ToolCallingService

        tools = []

        # 1. Add built-in tools
        for tool_name in agent.tools_config.get("builtin_tools", []):
            tool = BuiltinToolRegistry.get(tool_name)
            if tool:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters_schema
                    }
                })

        # 2. Add MCP server tools
        mcp_servers = agent.tools_config.get("mcp_servers", [])
        if mcp_servers:
            mcp_service = MCPServerService(db)
            for server_name in mcp_servers:
                server = await mcp_service.get_server_by_name(server_name, user_id)
                if server and server.is_active and server.cached_tools:
                    for mcp_tool in server.cached_tools:
                        # Enhance MCP tool description with server context
                        original_desc = mcp_tool["function"].get("description", "")
                        enhanced_desc = f"[MCP: {server_name}] {original_desc} (Use this tool for {server_name}-specific queries.)"
                        tool_copy = {
                            "type": "function",
                            "function": {
                                "name": f"{server_name}.{mcp_tool['function']['name']}",
                                "description": enhanced_desc,
                                "parameters": mcp_tool["function"].get("parameters", {
                                    "type": "object",
                                    "properties": {},
                                    "required": []
                                })
                            }
                        }
                        tools.append(tool_copy)

        # 3. Add custom tools if enabled
        include_custom_tools = agent.tools_config.get("include_custom_tools", True)
        if include_custom_tools:
            tool_calling_service = ToolCallingService(db)
            custom_tools = await tool_calling_service._get_available_tools_for_user(
                current_user, include_builtin=False
            )
            custom_tools_formatted = await tool_calling_service._convert_tools_to_openai_format(
                custom_tools
            )
            tools.extend(custom_tools_formatted)

        # Create chat request
        chat_request = ChatRequest(
            model=agent.model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice=agent.tools_config.get("tool_choice", "auto") if tools else None,
            temperature=agent.temperature,  # Already 0.0-2.0 range
            max_tokens=agent.max_tokens,
            user_id=str(user_id),
            api_key_id=1
        )

        # Execute via ToolCallingService
        service = ToolCallingService(db)
        response = await service.create_chat_completion_with_tools(
            request=chat_request,
            user=current_user,
            max_tool_calls=agent.tools_config.get("max_iterations", 5),
            tool_resources=agent.tool_resources
        )

        # Extract assistant message
        assistant_msg = response.choices[0].message

        # Save assistant message
        tool_calls_data = None
        if assistant_msg.tool_calls:
            tool_calls_data = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": tc.function
                }
                for tc in assistant_msg.tool_calls
            ]

        await self.save_agent_message(
            conversation.id,
            "assistant",
            assistant_msg.content,
            tool_calls_data,
            db
        )

        # Update agent usage
        agent.usage_count += 1
        agent.last_used_at = datetime.utcnow()
        await db.commit()

        # Return OpenAI-compatible response
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        # Build tool_calls for response if present
        response_tool_calls = None
        if assistant_msg.tool_calls:
            response_tool_calls = [
                ToolCall(
                    id=tc.id,
                    type=tc.type,
                    function=tc.function
                )
                for tc in assistant_msg.tool_calls
            ]

        # Determine finish_reason based on whether tool calls were made
        finish_reason = "tool_calls" if response_tool_calls else "stop"

        return AgentChatCompletionResponse(
            id=f"agent-{agent.id}-{int(time.time())}",
            object="chat.completion",
            created=int(time.time()),
            model=agent.model,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=assistant_msg.content,
                        tool_calls=response_tool_calls
                    ),
                    finish_reason=finish_reason
                )
            ],
            usage=ChatUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )

    async def chat_completion_openai(
        self,
        agent_id: int,
        request: AgentChatCompletionRequest,
        api_key: APIKey,
        db: AsyncSession
    ) -> AgentChatCompletionResponse:
        """OpenAI-compatible chat completion for agents with API key auth."""
        # Check if API key can access this agent
        if not api_key.can_access_agent(agent_id):
            raise HTTPException(
                status_code=403,
                detail="API key not authorized to access this agent"
            )

        # Create user context from API key
        user_context = {"id": api_key.user_id}

        # Load agent config
        agent = await self.get_agent_config_by_id(agent_id, user_context, db)

        # Find the last user message
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(
                status_code=400,
                detail="No user message found in conversation"
            )

        last_user_message = user_messages[-1].content

        # Get or create conversation using a hash of messages
        import hashlib
        conv_hash = hashlib.md5(
            str([f"{msg.role}:{msg.content}" for msg in request.messages]).encode()
        ).hexdigest()[:16]

        conversation = await self.get_or_create_conversation(
            conv_hash, agent.id, api_key.user_id, db
        )

        # Save user message
        await self.save_agent_message(
            conversation.id,
            "user",
            last_user_message,
            None,
            db
        )

        # Build messages for LLM - use request messages as history
        messages = []
        if agent.system_prompt:
            messages.append(ChatMessage(role="system", content=agent.system_prompt))

        # Add conversation messages from request
        for msg in request.messages:
            if msg.role in ["user", "assistant"]:
                messages.append(ChatMessage(role=msg.role, content=msg.content))

        # Build tools from agent config
        from app.services.builtin_tools.registry import BuiltinToolRegistry
        from app.services.mcp_server_service import MCPServerService
        from app.services.tool_calling_service import ToolCallingService

        tools = []

        # 1. Add built-in tools
        for tool_name in agent.tools_config.get("builtin_tools", []):
            tool = BuiltinToolRegistry.get(tool_name)
            if tool:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters_schema
                    }
                })

        # 2. Add MCP server tools
        mcp_servers = agent.tools_config.get("mcp_servers", [])
        if mcp_servers:
            mcp_service = MCPServerService(db)
            for server_name in mcp_servers:
                server = await mcp_service.get_server_by_name(server_name, api_key.user_id)
                if server and server.is_active and server.cached_tools:
                    for mcp_tool in server.cached_tools:
                        # Enhance MCP tool description with server context
                        original_desc = mcp_tool["function"].get("description", "")
                        enhanced_desc = f"[MCP: {server_name}] {original_desc} (Use this tool for {server_name}-specific queries.)"
                        tool_copy = {
                            "type": "function",
                            "function": {
                                "name": f"{server_name}.{mcp_tool['function']['name']}",
                                "description": enhanced_desc,
                                "parameters": mcp_tool["function"].get("parameters", {
                                    "type": "object",
                                    "properties": {},
                                    "required": []
                                })
                            }
                        }
                        tools.append(tool_copy)

        # 3. Add custom tools if enabled
        include_custom_tools = agent.tools_config.get("include_custom_tools", True)
        if include_custom_tools:
            tool_calling_service = ToolCallingService(db)
            custom_tools = await tool_calling_service._get_available_tools_for_user(
                user_context, include_builtin=False
            )
            custom_tools_formatted = await tool_calling_service._convert_tools_to_openai_format(
                custom_tools
            )
            tools.extend(custom_tools_formatted)

        # Apply request overrides
        temperature = request.temperature if request.temperature is not None else agent.temperature
        max_tokens = request.max_tokens if request.max_tokens is not None else agent.max_tokens

        # Create chat request
        from app.services.llm.models import ChatRequest as LLMChatRequest, ChatMessage as LLMChatMessage
        llm_messages = [LLMChatMessage(role=m.role, content=m.content) for m in messages]

        chat_request = LLMChatRequest(
            model=agent.model,
            messages=llm_messages,
            tools=tools if tools else None,
            tool_choice=agent.tools_config.get("tool_choice", "auto") if tools else None,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=str(api_key.user_id),
            api_key_id=api_key.id
        )

        # Execute via ToolCallingService
        service = ToolCallingService(db)
        response = await service.create_chat_completion_with_tools(
            request=chat_request,
            user=user_context,
            max_tool_calls=agent.tools_config.get("max_iterations", 5),
            tool_resources=agent.tool_resources
        )

        # Extract assistant message
        assistant_msg = response.choices[0].message

        # Save assistant message
        tool_calls_data = None
        if assistant_msg.tool_calls:
            tool_calls_data = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": tc.function
                }
                for tc in assistant_msg.tool_calls
            ]

        await self.save_agent_message(
            conversation.id,
            "assistant",
            assistant_msg.content,
            tool_calls_data,
            db
        )

        # Update agent usage
        agent.usage_count += 1
        agent.last_used_at = datetime.utcnow()

        # Update API key usage
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0
        api_key.update_usage(tokens_used=prompt_tokens + completion_tokens, cost_cents=0)
        await db.commit()

        # Build tool_calls for response if present
        response_tool_calls = None
        if assistant_msg.tool_calls:
            response_tool_calls = [
                ToolCall(
                    id=tc.id,
                    type=tc.type,
                    function=tc.function
                )
                for tc in assistant_msg.tool_calls
            ]

        # Determine finish_reason based on whether tool calls were made
        finish_reason = "tool_calls" if response_tool_calls else "stop"

        return AgentChatCompletionResponse(
            id=f"agent-{agent.id}-{int(time.time())}",
            object="chat.completion",
            created=int(time.time()),
            model=agent.model,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=assistant_msg.content,
                        tool_calls=response_tool_calls
                    ),
                    finish_reason=finish_reason
                )
            ],
            usage=ChatUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )

    # ========================================================================
    # FastAPI Router
    # ========================================================================

    def get_router(self) -> APIRouter:
        """Get FastAPI router for agent endpoints"""
        router = APIRouter(prefix="/agent", tags=["agent"])

        @router.post("/configs", status_code=201)
        async def create_agent_config_endpoint(
            request: AgentConfigCreate,
            db: AsyncSession = Depends(get_db),
            current_user: Dict[str, Any] = Depends(get_current_user),
        ):
            """Create a new agent configuration."""
            user_id = _get_user_id(current_user)
            return await self.create_agent_config(request, user_id, db)

        @router.get("/configs")
        async def list_agent_configs_endpoint(
            category: Optional[str] = Query(None),
            is_public: Optional[bool] = Query(None),
            db: AsyncSession = Depends(get_db),
            current_user: Dict[str, Any] = Depends(get_current_user),
        ):
            """List agent configurations accessible to the user."""
            user_id = _get_user_id(current_user)
            return await self.list_agent_configs(user_id, category, is_public, db)

        @router.get("/configs/{config_id}")
        async def get_agent_config_endpoint(
            config_id: int,
            db: AsyncSession = Depends(get_db),
            current_user: Dict[str, Any] = Depends(get_current_user),
        ):
            """Get a specific agent configuration."""
            config = await self.get_agent_config_by_id(config_id, current_user, db)
            return config.to_dict()

        @router.put("/configs/{config_id}")
        async def update_agent_config_endpoint(
            config_id: int,
            request: AgentConfigUpdate,
            db: AsyncSession = Depends(get_db),
            current_user: Dict[str, Any] = Depends(get_current_user),
        ):
            """Update an agent configuration."""
            user_id = _get_user_id(current_user)
            return await self.update_agent_config(config_id, request, user_id, db)

        @router.delete("/configs/{config_id}")
        async def delete_agent_config_endpoint(
            config_id: int,
            db: AsyncSession = Depends(get_db),
            current_user: Dict[str, Any] = Depends(get_current_user),
        ):
            """Delete an agent configuration."""
            user_id = _get_user_id(current_user)
            return await self.delete_agent_config(config_id, user_id, db)

        # OpenAI-compatible chat completions endpoint (external API with API key auth)
        @router.post(
            "/{agent_id}/v1/chat/completions",
            response_model=AgentChatCompletionResponse
        )
        async def agent_chat_completions(
            agent_id: int,
            request: AgentChatCompletionRequest,
            api_key: APIKey = Depends(get_api_key_auth),
            db: AsyncSession = Depends(get_db),
        ):
            """OpenAI-compatible chat completions endpoint for agents."""
            return await self.chat_completion_openai(agent_id, request, api_key, db)

        # Internal chat endpoint (JWT auth for frontend)
        @router.post(
            "/{agent_id}/chat/completions",
            response_model=AgentChatCompletionResponse
        )
        async def agent_chat_completions_internal(
            agent_id: int,
            request: AgentChatCompletionRequest,
            db: AsyncSession = Depends(get_db),
            current_user: Dict[str, Any] = Depends(get_current_user),
            api_key_context: Optional[Dict[str, Any]] = Depends(get_api_key_context),
        ):
            """Internal chat completions endpoint for agents (JWT auth)."""
            user_id = _get_user_id(current_user)

            # Find the last user message
            user_messages = [msg for msg in request.messages if msg.role == "user"]
            if not user_messages:
                raise HTTPException(
                    status_code=400,
                    detail="No user message found in conversation"
                )

            last_user_message = user_messages[-1].content

            # Load agent config
            agent = await self.get_agent_config_by_id(agent_id, current_user, db)

            # Check API key access restrictions if using API key authentication
            if api_key_context:
                api_key = api_key_context.get("api_key")
                if api_key and not api_key.can_access_agent(agent_id):
                    raise HTTPException(
                        status_code=403,
                        detail="API key not authorized to access this agent"
                    )

            # Get or create conversation using a hash of messages
            import hashlib
            conv_hash = hashlib.md5(
                str([f"{msg.role}:{msg.content}" for msg in request.messages]).encode()
            ).hexdigest()[:16]

            conversation = await self.get_or_create_conversation(
                conv_hash, agent.id, user_id, db
            )

            # Save user message
            await self.save_agent_message(
                conversation.id,
                "user",
                last_user_message,
                None,
                db
            )

            # Build messages for LLM
            messages = []
            if agent.system_prompt:
                messages.append(ChatMessage(role="system", content=agent.system_prompt))

            for msg in request.messages:
                if msg.role in ["user", "assistant"]:
                    messages.append(ChatMessage(role=msg.role, content=msg.content))

            # Build tools from agent config
            from app.services.builtin_tools.registry import BuiltinToolRegistry
            from app.services.mcp_server_service import MCPServerService
            from app.services.tool_calling_service import ToolCallingService

            tools = []

            for tool_name in agent.tools_config.get("builtin_tools", []):
                tool = BuiltinToolRegistry.get(tool_name)
                if tool:
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters_schema
                        }
                    })

            mcp_servers = agent.tools_config.get("mcp_servers", [])
            if mcp_servers:
                mcp_service = MCPServerService(db)
                for server_name in mcp_servers:
                    server = await mcp_service.get_server_by_name(server_name, user_id)
                    if server and server.is_active and server.cached_tools:
                        for mcp_tool in server.cached_tools:
                            # Enhance MCP tool description with server context
                            original_desc = mcp_tool["function"].get("description", "")
                            enhanced_desc = f"[MCP: {server_name}] {original_desc} (Use this tool for {server_name}-specific queries.)"
                            tool_copy = {
                                "type": "function",
                                "function": {
                                    "name": f"{server_name}.{mcp_tool['function']['name']}",
                                    "description": enhanced_desc,
                                    "parameters": mcp_tool["function"].get("parameters", {
                                        "type": "object",
                                        "properties": {},
                                        "required": []
                                    })
                                }
                            }
                            tools.append(tool_copy)

            include_custom_tools = agent.tools_config.get("include_custom_tools", True)
            if include_custom_tools:
                tool_calling_service = ToolCallingService(db)
                custom_tools = await tool_calling_service._get_available_tools_for_user(
                    current_user, include_builtin=False
                )
                custom_tools_formatted = await tool_calling_service._convert_tools_to_openai_format(
                    custom_tools
                )
                tools.extend(custom_tools_formatted)

            # Apply request overrides
            temperature = request.temperature if request.temperature is not None else agent.temperature
            max_tokens = request.max_tokens if request.max_tokens is not None else agent.max_tokens

            # Create chat request
            from app.services.llm.models import ChatRequest as LLMChatRequest, ChatMessage as LLMChatMessage
            llm_messages = [LLMChatMessage(role=m.role, content=m.content) for m in messages]

            chat_request = LLMChatRequest(
                model=agent.model,
                messages=llm_messages,
                tools=tools if tools else None,
                tool_choice=agent.tools_config.get("tool_choice", "auto") if tools else None,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=str(user_id),
                api_key_id=1
            )

            # Execute via ToolCallingService
            service = ToolCallingService(db)
            response = await service.create_chat_completion_with_tools(
                request=chat_request,
                user=current_user,
                max_tool_calls=agent.tools_config.get("max_iterations", 5),
                tool_resources=agent.tool_resources
            )

            # Extract assistant message
            assistant_msg = response.choices[0].message

            # Save assistant message
            tool_calls_data = None
            if assistant_msg.tool_calls:
                tool_calls_data = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": tc.function
                    }
                    for tc in assistant_msg.tool_calls
                ]

            await self.save_agent_message(
                conversation.id,
                "assistant",
                assistant_msg.content,
                tool_calls_data,
                db
            )

            # Update agent usage
            agent.usage_count += 1
            agent.last_used_at = datetime.utcnow()
            await db.commit()

            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0

            return AgentChatCompletionResponse(
                id=f"agent-{agent.id}-{int(time.time())}",
                object="chat.completion",
                created=int(time.time()),
                model=agent.model,
                choices=[
                    ChatChoice(
                        index=0,
                        message=ChatMessage(
                            role="assistant",
                            content=assistant_msg.content or ""
                        ),
                        finish_reason="stop"
                    )
                ],
                usage=ChatUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                )
            )

        return router


# ============================================================================
# Module Factory
# ============================================================================

def create_module(rag_service: Optional[RAGServiceProtocol] = None) -> AgentModule:
    """Factory function to create agent module instance"""
    return AgentModule(rag_service=rag_service)


# Create module instance (dependencies will be injected via factory)
agent_module = AgentModule()
