"""
Prompts API Endpoints

Exposes AgentConfig as "Prompts" for OpenAI SDK compatibility.
This provides a programmatic way to manage agent configurations.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.models.agent_config import AgentConfig
from app.services.api_key_auth import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================

class PromptCreateRequest(BaseModel):
    """Request to create a prompt (agent config)"""
    name: str = Field(..., min_length=1, max_length=200)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    instructions: str = Field(..., min_length=1)  # System prompt
    model: str = Field(default="gpt-oss-120b")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, gt=0)
    tools: Optional[List[Dict[str, Any]]] = None  # Tool definitions
    tool_resources: Optional[Dict[str, Any]] = None  # OpenAI format
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: bool = False
    metadata: Optional[Dict[str, Any]] = None


class PromptUpdateRequest(BaseModel):
    """Request to update a prompt"""
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    instructions: Optional[str] = Field(None, min_length=1)
    model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    tools: Optional[List[Dict[str, Any]]] = None
    tool_resources: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None


class PromptResponse(BaseModel):
    """Prompt (agent config) response"""
    id: int
    name: str
    display_name: str
    description: Optional[str]
    instructions: str
    model: str
    temperature: float
    max_tokens: int
    tools_config: Dict[str, Any]
    tool_resources: Optional[Dict[str, Any]]
    category: Optional[str]
    tags: List[str]
    is_public: bool
    is_template: bool
    is_active: bool
    usage_count: int
    created_at: Optional[str]
    updated_at: Optional[str]
    last_used_at: Optional[str]


class PromptListResponse(BaseModel):
    """List of prompts"""
    object: str = "list"
    data: List[PromptResponse]
    has_more: bool = False


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/prompts",
    response_model=PromptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Prompt",
    description="Create a new prompt (agent configuration).",
    tags=["Prompts API"]
)
async def create_prompt(
    request: PromptCreateRequest,
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
) -> PromptResponse:
    """Create a new prompt.

    Args:
        request: Prompt creation request
        api_key_context: API key authentication context
        db: Database session

    Returns:
        Created prompt

    Raises:
        HTTPException: If creation fails or name already exists
    """
    try:
        user = api_key_context.get("user")

        # Check if name already exists for this user
        stmt = select(AgentConfig).where(
            AgentConfig.name == request.name,
            AgentConfig.created_by_user_id == user.id
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Prompt with name '{request.name}' already exists"
            )

        # Convert tools to tools_config format
        tools_config = {}
        if request.tools:
            builtin_tools = []
            mcp_servers = []

            for tool in request.tools:
                tool_type = tool.get("type")
                if tool_type == "file_search":
                    builtin_tools.append("rag_search")
                elif tool_type == "web_search":
                    builtin_tools.append("web_search")
                elif tool_type == "mcp":
                    server_name = tool.get("server")
                    if server_name:
                        mcp_servers.append(server_name)

            if builtin_tools:
                tools_config["builtin_tools"] = builtin_tools
            if mcp_servers:
                tools_config["mcp_servers"] = mcp_servers

        # Create agent config
        agent_config = AgentConfig(
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            system_prompt=request.instructions,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tools_config=tools_config or {},
            tool_resources=request.tool_resources,
            category=request.category,
            tags=request.tags or [],
            is_public=request.is_public,
            is_template=False,
            created_by_user_id=user.id,
            is_active=True
        )

        db.add(agent_config)
        await db.commit()
        await db.refresh(agent_config)

        logger.info(f"Created prompt (agent config) {agent_config.name}")

        # Convert to response
        return PromptResponse(
            id=agent_config.id,
            name=agent_config.name,
            display_name=agent_config.display_name,
            description=agent_config.description,
            instructions=agent_config.system_prompt,
            model=agent_config.model,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
            tools_config=agent_config.tools_config,
            tool_resources=agent_config.tool_resources,
            category=agent_config.category,
            tags=agent_config.tags or [],
            is_public=agent_config.is_public,
            is_template=agent_config.is_template,
            is_active=agent_config.is_active,
            usage_count=agent_config.usage_count,
            created_at=agent_config.created_at.isoformat() if agent_config.created_at else None,
            updated_at=agent_config.updated_at.isoformat() if agent_config.updated_at else None,
            last_used_at=agent_config.last_used_at.isoformat() if agent_config.last_used_at else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating prompt: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create prompt: {str(e)}"
        )


@router.get(
    "/prompts",
    response_model=PromptListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Prompts",
    description="List all prompts accessible to the user.",
    tags=["Prompts API"]
)
async def list_prompts(
    limit: int = Query(default=20, ge=1, le=100),
    category: Optional[str] = Query(default=None),
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
) -> PromptListResponse:
    """List prompts.

    Args:
        limit: Maximum number to return
        category: Filter by category
        api_key_context: API key authentication context
        db: Database session

    Returns:
        List of prompts
    """
    try:
        user = api_key_context.get("user")

        # Build query - user's own prompts + public prompts
        stmt = select(AgentConfig).where(
            AgentConfig.is_active == True,
            (
                (AgentConfig.created_by_user_id == user.id) |
                (AgentConfig.is_public == True)
            )
        ).order_by(AgentConfig.created_at.desc()).limit(limit)

        # Apply category filter
        if category:
            stmt = stmt.where(AgentConfig.category == category)

        result = await db.execute(stmt)
        agent_configs = result.scalars().all()

        # Convert to response
        data = [
            PromptResponse(
                id=ac.id,
                name=ac.name,
                display_name=ac.display_name,
                description=ac.description,
                instructions=ac.system_prompt,
                model=ac.model,
                temperature=ac.temperature,
                max_tokens=ac.max_tokens,
                tools_config=ac.tools_config,
                tool_resources=ac.tool_resources,
                category=ac.category,
                tags=ac.tags or [],
                is_public=ac.is_public,
                is_template=ac.is_template,
                is_active=ac.is_active,
                usage_count=ac.usage_count,
                created_at=ac.created_at.isoformat() if ac.created_at else None,
                updated_at=ac.updated_at.isoformat() if ac.updated_at else None,
                last_used_at=ac.last_used_at.isoformat() if ac.last_used_at else None
            )
            for ac in agent_configs
        ]

        return PromptListResponse(
            object="list",
            data=data,
            has_more=len(agent_configs) == limit
        )

    except Exception as e:
        logger.error(f"Error listing prompts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list prompts: {str(e)}"
        )


@router.get(
    "/prompts/{prompt_id}",
    response_model=PromptResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Prompt",
    description="Get a prompt by ID or name.",
    tags=["Prompts API"]
)
async def get_prompt(
    prompt_id: str,
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
) -> PromptResponse:
    """Get a prompt by ID or name.

    Args:
        prompt_id: Prompt ID (integer) or name (string)
        api_key_context: API key authentication context
        db: Database session

    Returns:
        Prompt

    Raises:
        HTTPException: If prompt not found
    """
    try:
        user = api_key_context.get("user")

        # Try by ID first, then by name
        try:
            id_int = int(prompt_id)
            stmt = select(AgentConfig).where(
                AgentConfig.id == id_int,
                AgentConfig.is_active == True,
                (
                    (AgentConfig.created_by_user_id == user.id) |
                    (AgentConfig.is_public == True)
                )
            )
        except ValueError:
            # Not a number, search by name
            stmt = select(AgentConfig).where(
                AgentConfig.name == prompt_id,
                AgentConfig.is_active == True,
                (
                    (AgentConfig.created_by_user_id == user.id) |
                    (AgentConfig.is_public == True)
                )
            )

        result = await db.execute(stmt)
        agent_config = result.scalar_one_or_none()

        if not agent_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt '{prompt_id}' not found"
            )

        return PromptResponse(
            id=agent_config.id,
            name=agent_config.name,
            display_name=agent_config.display_name,
            description=agent_config.description,
            instructions=agent_config.system_prompt,
            model=agent_config.model,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
            tools_config=agent_config.tools_config,
            tool_resources=agent_config.tool_resources,
            category=agent_config.category,
            tags=agent_config.tags or [],
            is_public=agent_config.is_public,
            is_template=agent_config.is_template,
            is_active=agent_config.is_active,
            usage_count=agent_config.usage_count,
            created_at=agent_config.created_at.isoformat() if agent_config.created_at else None,
            updated_at=agent_config.updated_at.isoformat() if agent_config.updated_at else None,
            last_used_at=agent_config.last_used_at.isoformat() if agent_config.last_used_at else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prompt: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prompt: {str(e)}"
        )


@router.put(
    "/prompts/{prompt_id}",
    response_model=PromptResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Prompt",
    description="Update a prompt by ID.",
    tags=["Prompts API"]
)
async def update_prompt(
    prompt_id: int,
    request: PromptUpdateRequest,
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
) -> PromptResponse:
    """Update a prompt.

    Args:
        prompt_id: Prompt ID
        request: Update request
        api_key_context: API key authentication context
        db: Database session

    Returns:
        Updated prompt

    Raises:
        HTTPException: If prompt not found or not owned by user
    """
    try:
        user = api_key_context.get("user")

        stmt = select(AgentConfig).where(
            AgentConfig.id == prompt_id,
            AgentConfig.created_by_user_id == user.id
        )
        result = await db.execute(stmt)
        agent_config = result.scalar_one_or_none()

        if not agent_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt {prompt_id} not found or not owned by user"
            )

        # Update fields
        if request.display_name is not None:
            agent_config.display_name = request.display_name
        if request.description is not None:
            agent_config.description = request.description
        if request.instructions is not None:
            agent_config.system_prompt = request.instructions
        if request.model is not None:
            agent_config.model = request.model
        if request.temperature is not None:
            agent_config.temperature = request.temperature
        if request.max_tokens is not None:
            agent_config.max_tokens = request.max_tokens
        if request.category is not None:
            agent_config.category = request.category
        if request.tags is not None:
            agent_config.tags = request.tags
        if request.is_public is not None:
            agent_config.is_public = request.is_public
        if request.is_active is not None:
            agent_config.is_active = request.is_active

        # Update tools config
        if request.tools is not None:
            tools_config = {}
            builtin_tools = []
            mcp_servers = []

            for tool in request.tools:
                tool_type = tool.get("type")
                if tool_type == "file_search":
                    builtin_tools.append("rag_search")
                elif tool_type == "web_search":
                    builtin_tools.append("web_search")
                elif tool_type == "mcp":
                    server_name = tool.get("server")
                    if server_name:
                        mcp_servers.append(server_name)

            if builtin_tools:
                tools_config["builtin_tools"] = builtin_tools
            if mcp_servers:
                tools_config["mcp_servers"] = mcp_servers

            agent_config.tools_config = tools_config

        if request.tool_resources is not None:
            agent_config.tool_resources = request.tool_resources

        await db.commit()
        await db.refresh(agent_config)

        logger.info(f"Updated prompt {prompt_id}")

        return PromptResponse(
            id=agent_config.id,
            name=agent_config.name,
            display_name=agent_config.display_name,
            description=agent_config.description,
            instructions=agent_config.system_prompt,
            model=agent_config.model,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
            tools_config=agent_config.tools_config,
            tool_resources=agent_config.tool_resources,
            category=agent_config.category,
            tags=agent_config.tags or [],
            is_public=agent_config.is_public,
            is_template=agent_config.is_template,
            is_active=agent_config.is_active,
            usage_count=agent_config.usage_count,
            created_at=agent_config.created_at.isoformat() if agent_config.created_at else None,
            updated_at=agent_config.updated_at.isoformat() if agent_config.updated_at else None,
            last_used_at=agent_config.last_used_at.isoformat() if agent_config.last_used_at else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating prompt: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update prompt: {str(e)}"
        )


@router.delete(
    "/prompts/{prompt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Prompt",
    description="Delete a prompt by ID.",
    tags=["Prompts API"]
)
async def delete_prompt(
    prompt_id: int,
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Delete a prompt.

    Args:
        prompt_id: Prompt ID
        api_key_context: API key authentication context
        db: Database session

    Raises:
        HTTPException: If prompt not found or not owned by user
    """
    try:
        user = api_key_context.get("user")

        stmt = delete(AgentConfig).where(
            AgentConfig.id == prompt_id,
            AgentConfig.created_by_user_id == user.id
        )
        result = await db.execute(stmt)
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt {prompt_id} not found or not owned by user"
            )

        logger.info(f"Deleted prompt {prompt_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting prompt: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete prompt: {str(e)}"
        )
