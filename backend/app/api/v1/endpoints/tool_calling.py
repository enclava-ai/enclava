"""
Tool calling API endpoints
Integration between LLM and tool execution
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.core.security import get_current_user
from app.services.tool_calling_service import ToolCallingService
from app.services.llm.models import ChatRequest, ChatResponse, ChatMessage
from app.schemas.tool_calling import (
    ToolCallRequest,
    ToolCallResponse,
    ToolExecutionRequest,
    ToolValidationRequest,
    ToolValidationResponse,
    ToolHistoryResponse,
)
from app.models.agent_config import AgentConfig
from app.models.chatbot import ChatbotConversation, ChatbotMessage
from app.models.user import User
from app.services.agent_init import AGENT_CHATBOT_ID
import uuid

router = APIRouter()


@router.post("/chat/completions", response_model=ChatResponse)
async def create_chat_completion_with_tools(
    request: ChatRequest,
    auto_execute_tools: bool = Query(
        True, description="Whether to automatically execute tool calls"
    ),
    max_tool_calls: int = Query(
        5, ge=1, le=10, description="Maximum number of tool calls"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create chat completion with tool calling support"""

    service = ToolCallingService(db)

    # Resolve user ID for context
    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    # Set user context in request
    request.user_id = str(user_id)
    request.api_key_id = 1  # Default for internal usage

    response = await service.create_chat_completion_with_tools(
        request=request,
        user=current_user,
        auto_execute_tools=auto_execute_tools,
        max_tool_calls=max_tool_calls,
    )

    return response


@router.post("/chat/completions/stream")
async def create_chat_completion_stream_with_tools(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create streaming chat completion with tool calling support"""

    service = ToolCallingService(db)

    # Resolve user ID for context
    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    # Set user context in request
    request.user_id = str(user_id)
    request.api_key_id = 1  # Default for internal usage

    async def stream_generator():
        async for chunk in service.create_chat_completion_stream_with_tools(
            request=request, user=current_user
        ):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/execute", response_model=ToolCallResponse)
async def execute_tool_by_name(
    request: ToolExecutionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Execute a tool by name directly"""

    service = ToolCallingService(db)

    try:
        result = await service.execute_tool_by_name(
            tool_name=request.tool_name,
            parameters=request.parameters,
            user=current_user,
        )

        return ToolCallResponse(success=True, result=result, error=None)

    except Exception as e:
        return ToolCallResponse(success=False, result=None, error=str(e))


@router.post("/validate", response_model=ToolValidationResponse)
async def validate_tool_availability(
    request: ToolValidationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Validate which tools are available to the user"""

    service = ToolCallingService(db)

    availability = await service.validate_tool_availability(
        tool_names=request.tool_names, user=current_user
    )

    return ToolValidationResponse(tool_availability=availability)


@router.get("/history", response_model=ToolHistoryResponse)
async def get_tool_call_history(
    limit: int = Query(
        50, ge=1, le=100, description="Number of history items to return"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get recent tool execution history for the user"""

    service = ToolCallingService(db)

    history = await service.get_tool_call_history(user=current_user, limit=limit)

    return ToolHistoryResponse(history=history, total=len(history))


@router.get("/available")
async def get_available_tools(
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get tools available for function calling"""

    service = ToolCallingService(db)

    # Get available tools
    tools = await service._get_available_tools_for_user(current_user)

    # Convert to OpenAI format
    openai_tools = await service._convert_tools_to_openai_format(tools)

    return {"tools": openai_tools, "count": len(openai_tools)}


# ============================================================================
# Agent Config Endpoints
# ============================================================================

# Pydantic Schemas for Agent Configs

class AgentConfigCreate(BaseModel):
    """Schema for creating an agent config."""
    name: str = Field(..., min_length=1, max_length=200)
    display_name: str = Field(..., min_length=1, max_length=200)
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


class AgentConfigUpdate(BaseModel):
    """Schema for updating an agent config."""
    name: Optional[str] = None
    display_name: Optional[str] = None
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


class AgentChatRequest(BaseModel):
    """Request to chat with an agent."""
    agent_config_id: int
    message: str
    conversation_id: Optional[str] = None


class AgentChatResponse(BaseModel):
    """Response from chatting with an agent."""
    content: Optional[str]
    conversation_id: str
    tool_calls_made: List[Dict[str, Any]] = Field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None


# Helper functions

async def get_agent_config_by_id(
    config_id: int,
    current_user: Dict[str, Any],
    db: AsyncSession
) -> AgentConfig:
    """Load agent config by ID with access control."""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id

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
    conversation_id: str,
    user_id: int,
    db: AsyncSession
) -> List[ChatMessage]:
    """Load conversation history from ChatbotMessage table.

    Security: Verifies the conversation belongs to the user and is an agent chat
    before loading messages. Returns empty list if access is denied.
    """
    # Find conversation with ownership verification (defense in depth)
    conv_stmt = select(ChatbotConversation).where(
        ChatbotConversation.id == conversation_id,
        ChatbotConversation.user_id == str(user_id),
        ChatbotConversation.chatbot_id == AGENT_CHATBOT_ID
    )
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalar_one_or_none()

    if not conversation:
        return []

    # Load messages by timestamp
    msg_stmt = select(ChatbotMessage).where(
        ChatbotMessage.conversation_id == conversation.id
    ).order_by(ChatbotMessage.timestamp)
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
    conversation_id: Optional[str],
    user_id: int,
    db: AsyncSession
) -> ChatbotConversation:
    """Get existing conversation or create new one.

    Security: When retrieving an existing conversation, we verify:
    1. The conversation belongs to the current user
    2. The conversation is associated with the agent chatbot (not a regular chatbot)

    This prevents users from accessing or hijacking other users' conversations.
    """
    if conversation_id:
        # SECURITY: Filter by user_id AND chatbot_id to prevent conversation hijacking
        stmt = select(ChatbotConversation).where(
            ChatbotConversation.id == conversation_id,
            ChatbotConversation.user_id == str(user_id),
            ChatbotConversation.chatbot_id == AGENT_CHATBOT_ID
        )
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()
        if conv:
            return conv
        # If conversation_id was provided but not found/accessible,
        # create a new one rather than returning someone else's conversation

    # Create new conversation (use special agent chatbot_id for agent chats)
    new_conv = ChatbotConversation(
        id=str(uuid.uuid4()),
        chatbot_id=AGENT_CHATBOT_ID,  # References the special agent chatbot instance
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
    conversation_id: str,
    role: str,
    content: Optional[str],
    tool_calls: Optional[List[Dict[str, Any]]],
    db: AsyncSession
) -> ChatbotMessage:
    """Save a message to the conversation."""
    msg = ChatbotMessage(
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


# Agent Config CRUD Endpoints

@router.post("/agent/configs", status_code=201)
async def create_agent_config(
    request: AgentConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create a new agent configuration."""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id

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
        display_name=request.display_name,
        description=request.description,
        system_prompt=request.system_prompt,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        tools_config=tools_config,
        category=request.category,
        tags=request.tags,
        is_public=request.is_public,
        is_template=False,  # User-created configs are not templates
        created_by_user_id=user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return agent.to_dict()


@router.get("/agent/configs")
async def list_agent_configs(
    category: Optional[str] = Query(None),
    is_public: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List agent configurations accessible to the user."""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id

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


@router.get("/agent/configs/{config_id}")
async def get_agent_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get a specific agent configuration."""
    config = await get_agent_config_by_id(config_id, current_user, db)
    return config.to_dict()


@router.put("/agent/configs/{config_id}")
async def update_agent_config(
    config_id: int,
    request: AgentConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Update an agent configuration."""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id

    # Get config and verify ownership (not public configs)
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


@router.delete("/agent/configs/{config_id}")
async def delete_agent_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete an agent configuration."""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id

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

    await db.delete(config)
    await db.commit()

    return {"message": "Agent config deleted successfully"}


@router.post("/agent/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Chat with a pre-configured agent."""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id

    # Load agent config
    agent = await get_agent_config_by_id(request.agent_config_id, current_user, db)

    # Get or create conversation
    conversation = await get_or_create_conversation(request.conversation_id, user_id, db)

    # Save user message
    await save_agent_message(
        conversation.id,
        "user",
        request.message,
        None,
        db
    )

    # Load conversation history (with ownership verification)
    history = await load_conversation_history(conversation.id, user_id, db)

    # Build messages for LLM
    messages = []
    if agent.system_prompt:
        messages.append(ChatMessage(role="system", content=agent.system_prompt))
    messages.extend(history)

    # Build tools from agent config
    from app.services.builtin_tools.registry import BuiltinToolRegistry
    from app.services.mcp_server_service import MCPServerService
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
                # Add tools with server name prefix for routing
                for mcp_tool in server.cached_tools:
                    # Create a copy with prefixed name (server_name.tool_name)
                    tool_copy = {
                        "type": "function",
                        "function": {
                            "name": f"{server_name}.{mcp_tool['function']['name']}",
                            "description": mcp_tool["function"].get("description", ""),
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
            current_user, include_builtin=False  # Don't include builtins again
        )
        # Convert custom tools to OpenAI format
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
        temperature=agent.temperature / 10.0,
        max_tokens=agent.max_tokens,
        user_id=str(user_id),
        api_key_id=1
    )

    # Execute via ToolCallingService
    service = ToolCallingService(db)
    response = await service.create_chat_completion_with_tools(
        request=chat_request,
        user=current_user,
        max_tool_calls=agent.tools_config.get("max_iterations", 5)
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

    await save_agent_message(
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

    return AgentChatResponse(
        content=assistant_msg.content,
        conversation_id=conversation.id,
        tool_calls_made=tool_calls_data or [],
        usage=response.usage.dict() if response.usage else None
    )
