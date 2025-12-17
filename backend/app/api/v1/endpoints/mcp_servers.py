"""
MCP Server Management API endpoints.

Provides CRUD operations for MCP server configurations,
connection testing, and tool discovery.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.security import get_current_user
from app.core.logging import get_logger
from app.services.mcp_server_service import MCPServerService
from app.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerUpdate,
    MCPServerResponse,
    MCPServerListResponse,
    MCPServerTestRequest,
    MCPServerTestResponse,
    MCPServerRefreshResponse,
    MCPServerDeleteResponse,
)


logger = get_logger("api.mcp_servers")

router = APIRouter()


def _get_user_id(current_user: Dict[str, Any]) -> int:
    """Extract user ID from current_user dict or object."""
    return current_user.get("id") if isinstance(current_user, dict) else current_user.id


def _is_admin(current_user: Dict[str, Any]) -> bool:
    """Check if user is an admin."""
    if isinstance(current_user, dict):
        return current_user.get("is_superuser", False) or current_user.get("is_admin", False)
    return getattr(current_user, "is_superuser", False) or getattr(current_user, "is_admin", False)


# =============================================================================
# CRUD Endpoints
# =============================================================================


@router.post("", response_model=MCPServerResponse, status_code=201)
async def create_mcp_server(
    request: MCPServerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a new MCP server configuration.

    - All authenticated users can create their own MCP servers
    - Only admins can create global servers (is_global=true)
    """
    user_id = _get_user_id(current_user)
    is_admin = _is_admin(current_user)

    service = MCPServerService(db)

    try:
        server = await service.create_server(
            data=request,
            user_id=user_id,
            is_admin=is_admin
        )
        return MCPServerResponse(**server.to_dict())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("", response_model=MCPServerListResponse)
async def list_mcp_servers(
    include_inactive: bool = Query(False, description="Include inactive servers"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    List MCP servers accessible to the current user.

    Returns the user's own servers plus active global servers.
    Admins can see all servers.
    """
    user_id = _get_user_id(current_user)
    is_admin = _is_admin(current_user)

    service = MCPServerService(db)

    servers, user_count, global_count = await service.list_servers(
        user_id=user_id,
        is_admin=is_admin,
        include_inactive=include_inactive
    )

    return MCPServerListResponse(
        servers=[MCPServerResponse(**s.to_dict()) for s in servers],
        total=len(servers),
        user_servers=user_count,
        global_servers=global_count
    )


@router.get("/available")
async def get_available_mcp_servers(
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get simplified list of available MCP servers for agent configuration.

    Returns name, display_name, and tool_count for dropdown selection.
    """
    user_id = _get_user_id(current_user)

    service = MCPServerService(db)
    servers = await service.get_available_mcp_servers(user_id)

    return {"servers": servers, "count": len(servers)}


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get details of a specific MCP server.

    Users can only access their own servers and global servers.
    """
    user_id = _get_user_id(current_user)
    is_admin = _is_admin(current_user)

    service = MCPServerService(db)
    server = await service.get_server(
        server_id=server_id,
        user_id=user_id,
        is_admin=is_admin
    )

    if not server:
        raise HTTPException(
            status_code=404,
            detail="MCP server not found or access denied"
        )

    return MCPServerResponse(**server.to_dict())


@router.put("/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: int,
    request: MCPServerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update an MCP server configuration.

    Users can only update their own servers.
    Only admins can change the is_global flag.
    """
    user_id = _get_user_id(current_user)
    is_admin = _is_admin(current_user)

    service = MCPServerService(db)

    try:
        server = await service.update_server(
            server_id=server_id,
            data=request,
            user_id=user_id,
            is_admin=is_admin
        )

        if not server:
            raise HTTPException(
                status_code=404,
                detail="MCP server not found or access denied"
            )

        return MCPServerResponse(**server.to_dict())

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{server_id}", response_model=MCPServerDeleteResponse)
async def delete_mcp_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete an MCP server configuration.

    Users can only delete their own servers.
    Admins can delete any server.
    """
    user_id = _get_user_id(current_user)
    is_admin = _is_admin(current_user)

    service = MCPServerService(db)

    try:
        deleted = await service.delete_server(
            server_id=server_id,
            user_id=user_id,
            is_admin=is_admin
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="MCP server not found or access denied"
            )

        return MCPServerDeleteResponse(
            success=True,
            message="MCP server deleted successfully",
            deleted_id=server_id
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# =============================================================================
# Connection Testing Endpoints
# =============================================================================


@router.post("/test", response_model=MCPServerTestResponse)
async def test_mcp_connection(
    request: MCPServerTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Test connection to an MCP server and discover available tools.

    This endpoint can be used before saving a server configuration
    to verify the connection works and see what tools are available.
    """
    service = MCPServerService(db)
    response = await service.test_connection(request)
    return response


@router.post("/{server_id}/refresh-tools", response_model=MCPServerRefreshResponse)
async def refresh_server_tools(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Refresh the cached tools for an MCP server.

    Connects to the server and updates the cached tool list.
    """
    user_id = _get_user_id(current_user)
    is_admin = _is_admin(current_user)

    service = MCPServerService(db)
    response = await service.refresh_server_tools(
        server_id=server_id,
        user_id=user_id,
        is_admin=is_admin
    )

    return response
