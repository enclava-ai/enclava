"""
Tool management and execution API endpoints
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.security import get_current_user
from app.services.tool_management_service import ToolManagementService
from app.services.tool_execution_service import ToolExecutionService
from app.schemas.tool import (
    ToolCreate,
    ToolUpdate,
    ToolResponse,
    ToolListResponse,
    ToolExecutionCreate,
    ToolExecutionResponse,
    ToolExecutionListResponse,
    ToolCategoryCreate,
    ToolCategoryResponse,
    ToolStatisticsResponse,
)

router = APIRouter()


@router.post("/", response_model=ToolResponse)
async def create_tool(
    tool_data: ToolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create a new tool"""
    service = ToolManagementService(db)

    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    tool = await service.create_tool(
        name=tool_data.name,
        display_name=tool_data.display_name,
        code=tool_data.code,
        tool_type=tool_data.tool_type,
        created_by_user_id=user_id,
        description=tool_data.description,
        parameters_schema=tool_data.parameters_schema,
        return_schema=tool_data.return_schema,
        timeout_seconds=tool_data.timeout_seconds,
        max_memory_mb=tool_data.max_memory_mb,
        max_cpu_seconds=tool_data.max_cpu_seconds,
        docker_image=tool_data.docker_image,
        docker_command=tool_data.docker_command,
        category=tool_data.category,
        tags=tool_data.tags,
        is_public=tool_data.is_public,
    )

    return ToolResponse.from_orm(tool)


@router.get("/", response_model=ToolListResponse)
async def list_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None),
    tool_type: Optional[str] = Query(None),
    is_public: Optional[bool] = Query(None),
    is_approved: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    created_by_user_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List tools with filtering and pagination"""
    service = ToolManagementService(db)

    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    tools = await service.get_tools(
        user_id=user_id,
        skip=skip,
        limit=limit,
        category=category,
        tool_type=tool_type,
        is_public=is_public,
        is_approved=is_approved,
        search=search,
        tags=tags,
        created_by_user_id=created_by_user_id,
    )

    return ToolListResponse(
        tools=[ToolResponse.from_orm(tool) for tool in tools],
        total=len(tools),
        skip=skip,
        limit=limit,
    )


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get tool by ID"""
    service = ToolManagementService(db)

    tool = await service.get_tool_by_id(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    # Resolve underlying User object if available
    user_obj = (
        current_user.get("user_obj")
        if isinstance(current_user, dict)
        else current_user
    )

    # Check if user can access this tool
    if not user_obj or not tool.can_be_used_by(user_obj):
        raise HTTPException(status_code=403, detail="Access denied to this tool")

    return ToolResponse.from_orm(tool)


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: int,
    tool_data: ToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Update tool (only by creator or admin)"""
    service = ToolManagementService(db)

    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    tool = await service.update_tool(
        tool_id=tool_id,
        user_id=user_id,
        display_name=tool_data.display_name,
        description=tool_data.description,
        code=tool_data.code,
        parameters_schema=tool_data.parameters_schema,
        return_schema=tool_data.return_schema,
        timeout_seconds=tool_data.timeout_seconds,
        max_memory_mb=tool_data.max_memory_mb,
        max_cpu_seconds=tool_data.max_cpu_seconds,
        docker_image=tool_data.docker_image,
        docker_command=tool_data.docker_command,
        category=tool_data.category,
        tags=tool_data.tags,
        is_public=tool_data.is_public,
        is_active=tool_data.is_active,
    )

    return ToolResponse.from_orm(tool)


@router.delete("/{tool_id}")
async def delete_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete tool (only by creator or admin)"""
    service = ToolManagementService(db)

    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    await service.delete_tool(tool_id, user_id)
    return {"message": "Tool deleted successfully"}


@router.post("/{tool_id}/approve", response_model=ToolResponse)
async def approve_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Approve tool for public use (admin only)"""
    service = ToolManagementService(db)

    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    tool = await service.approve_tool(tool_id, user_id)
    return ToolResponse.from_orm(tool)


# Tool Execution Endpoints


@router.post("/{tool_id}/execute", response_model=ToolExecutionResponse)
async def execute_tool(
    tool_id: int,
    execution_data: ToolExecutionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Execute a tool with given parameters"""
    service = ToolExecutionService(db)

    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    execution = await service.execute_tool(
        tool_id=tool_id,
        user_id=user_id,
        parameters=execution_data.parameters,
        timeout_override=execution_data.timeout_override,
    )

    return ToolExecutionResponse.from_orm(execution)


@router.get("/executions", response_model=ToolExecutionListResponse)
async def list_executions(
    tool_id: Optional[int] = Query(None),
    executed_by_user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List tool executions with filtering"""
    service = ToolExecutionService(db)

    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    executions = await service.get_tool_executions(
        tool_id=tool_id,
        user_id=user_id,
        executed_by_user_id=executed_by_user_id,
        status=status,
        skip=skip,
        limit=limit,
    )

    return ToolExecutionListResponse(
        executions=[
            ToolExecutionResponse.from_orm(execution) for execution in executions
        ],
        total=len(executions),
        skip=skip,
        limit=limit,
    )


@router.get("/executions/{execution_id}", response_model=ToolExecutionResponse)
async def get_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get execution details"""
    service = ToolExecutionService(db)

    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    # Get execution through list with filter to ensure permission check
    executions = await service.get_tool_executions(
        user_id=user_id, skip=0, limit=1
    )

    execution = next((e for e in executions if e.id == execution_id), None)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return ToolExecutionResponse.from_orm(execution)


@router.post("/executions/{execution_id}/cancel", response_model=ToolExecutionResponse)
async def cancel_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Cancel a running execution"""
    service = ToolExecutionService(db)

    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    execution = await service.cancel_execution(execution_id, user_id)
    return ToolExecutionResponse.from_orm(execution)


@router.get("/executions/{execution_id}/logs")
async def get_execution_logs(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get real-time logs for execution"""
    service = ToolExecutionService(db)

    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    logs = await service.get_execution_logs(execution_id, user_id)
    return logs


# Tool Categories


@router.post("/categories", response_model=ToolCategoryResponse)
async def create_category(
    category_data: ToolCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create a new tool category (admin only)"""
    user_obj = (
        current_user.get("user_obj")
        if isinstance(current_user, dict)
        else current_user
    )

    if not user_obj or not user_obj.has_permission("manage_tools"):
        raise HTTPException(status_code=403, detail="Admin privileges required")

    service = ToolManagementService(db)

    category = await service.create_category(
        name=category_data.name,
        display_name=category_data.display_name,
        description=category_data.description,
        icon=category_data.icon,
        color=category_data.color,
        sort_order=category_data.sort_order,
    )

    return ToolCategoryResponse.from_orm(category)


@router.get("/categories", response_model=List[ToolCategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List all active tool categories"""
    service = ToolManagementService(db)

    categories = await service.get_categories()
    return [ToolCategoryResponse.from_orm(category) for category in categories]


# Statistics


@router.get("/statistics", response_model=ToolStatisticsResponse)
async def get_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get tool usage statistics"""
    service = ToolManagementService(db)

    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    stats = await service.get_tool_statistics(user_id=user_id)
    return ToolStatisticsResponse(**stats)
