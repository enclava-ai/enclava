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
from app.services.api_key_auth import get_api_key_context
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


@router.get("/agent/configs")
async def list_agent_configs(
    category: Optional[str] = Query(None),
    is_public: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List agent configurations accessible to the user.

    This endpoint is used by the API keys page to list available agents
    for access restriction configuration.
    """
    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    # Build query for agents accessible to the user
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
        "configs": [
            {
                "id": cfg.id,
                "name": cfg.name,
                "description": cfg.description,
            }
            for cfg in configs
        ],
        "count": len(configs)
    }
