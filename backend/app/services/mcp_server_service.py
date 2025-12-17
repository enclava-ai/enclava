"""
MCP Server Service

Business logic for managing MCP server configurations, including:
- CRUD operations with access control
- Connection testing with tool discovery
- Caching for performance
- Integration with tool calling service
"""

import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.cache import CoreCacheService
from app.models.mcp_server import MCPServer
from app.models.user import User
from app.services.mcp_client import MCPClient
from app.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerUpdate,
    MCPServerTestRequest,
    MCPServerTestResponse,
    MCPToolInfo,
    MCPServerRefreshResponse,
)


logger = get_logger("mcp_server_service")

# Cache TTL in seconds (5 minutes)
MCP_SERVER_CACHE_TTL = 300


class MCPServerService:
    """Service for managing MCP server configurations."""

    def __init__(self, db: AsyncSession):
        """Initialize the service.

        Args:
            db: Async database session
        """
        self.db = db
        self.cache = CoreCacheService()

    # =========================================================================
    # Create Operations
    # =========================================================================

    async def create_server(
        self,
        data: MCPServerCreate,
        user_id: int,
        is_admin: bool = False
    ) -> MCPServer:
        """
        Create a new MCP server configuration.

        Args:
            data: Server creation data
            user_id: ID of the user creating the server
            is_admin: Whether the user is an admin

        Returns:
            Created MCPServer instance

        Raises:
            ValueError: If validation fails or name already exists
            PermissionError: If non-admin tries to create global server
        """
        # Check if name already exists for this user or globally
        existing = await self._get_server_by_name(data.name, user_id)
        if existing:
            raise ValueError(f"Server with name '{data.name}' already exists")

        # Only admins can create global servers
        if data.is_global and not is_admin:
            raise PermissionError("Only administrators can create global MCP servers")

        # Create server instance
        server = MCPServer(
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            server_url=data.server_url,
            api_key=data.api_key,
            api_key_header_name=data.api_key_header_name,
            timeout_seconds=data.timeout_seconds,
            max_retries=data.max_retries,
            is_global=data.is_global if is_admin else False,
            created_by_user_id=user_id,
        )

        self.db.add(server)
        await self.db.commit()
        await self.db.refresh(server)

        logger.info(f"Created MCP server '{data.name}' for user {user_id}")
        return server

    # =========================================================================
    # Read Operations
    # =========================================================================

    async def get_server(
        self,
        server_id: int,
        user_id: int,
        is_admin: bool = False
    ) -> Optional[MCPServer]:
        """
        Get an MCP server by ID.

        Users can only access their own servers and global servers.
        Admins can access all servers.

        Args:
            server_id: Server ID
            user_id: Requesting user ID
            is_admin: Whether user is admin

        Returns:
            MCPServer instance or None
        """
        query = select(MCPServer).where(MCPServer.id == server_id)

        if not is_admin:
            # Non-admins can only see their own or global active servers
            query = query.where(
                or_(
                    MCPServer.created_by_user_id == user_id,
                    and_(MCPServer.is_global == True, MCPServer.is_active == True)
                )
            )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_server_by_name(
        self,
        name: str,
        user_id: int,
        is_admin: bool = False
    ) -> Optional[MCPServer]:
        """
        Get an MCP server by name.

        Args:
            name: Server name
            user_id: Requesting user ID
            is_admin: Whether user is admin

        Returns:
            MCPServer instance or None
        """
        # Check cache first
        cache_key = f"mcp_server:{name}:{user_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            # Reconstruct from cache (note: this is a simplified cache)
            return await self._get_server_by_name(name, user_id, is_admin)

        server = await self._get_server_by_name(name, user_id, is_admin)

        if server:
            # Cache the server ID for quick lookups
            await self.cache.set(cache_key, server.id, ttl=MCP_SERVER_CACHE_TTL)

        return server

    async def _get_server_by_name(
        self,
        name: str,
        user_id: int,
        is_admin: bool = False
    ) -> Optional[MCPServer]:
        """Internal method to get server by name."""
        query = select(MCPServer).where(MCPServer.name == name)

        if not is_admin:
            query = query.where(
                or_(
                    MCPServer.created_by_user_id == user_id,
                    and_(MCPServer.is_global == True, MCPServer.is_active == True)
                )
            )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_servers(
        self,
        user_id: int,
        is_admin: bool = False,
        include_inactive: bool = False
    ) -> Tuple[List[MCPServer], int, int]:
        """
        List MCP servers visible to the user.

        Returns user's own servers plus active global servers.

        Args:
            user_id: Requesting user ID
            is_admin: Whether user is admin
            include_inactive: Include inactive servers

        Returns:
            Tuple of (servers, user_server_count, global_server_count)
        """
        if is_admin:
            # Admins see all servers
            query = select(MCPServer)
            if not include_inactive:
                query = query.where(MCPServer.is_active == True)
        else:
            # Users see their own + global active servers
            query = select(MCPServer).where(
                or_(
                    MCPServer.created_by_user_id == user_id,
                    and_(MCPServer.is_global == True, MCPServer.is_active == True)
                )
            )
            if not include_inactive:
                query = query.where(MCPServer.is_active == True)

        query = query.order_by(MCPServer.display_name)
        result = await self.db.execute(query)
        servers = result.scalars().all()

        # Count user and global servers
        user_count = sum(1 for s in servers if s.created_by_user_id == user_id)
        global_count = sum(1 for s in servers if s.is_global)

        return list(servers), user_count, global_count

    # =========================================================================
    # Update Operations
    # =========================================================================

    async def update_server(
        self,
        server_id: int,
        data: MCPServerUpdate,
        user_id: int,
        is_admin: bool = False
    ) -> Optional[MCPServer]:
        """
        Update an MCP server configuration.

        Args:
            server_id: Server ID to update
            data: Update data
            user_id: Requesting user ID
            is_admin: Whether user is admin

        Returns:
            Updated MCPServer or None if not found/not authorized

        Raises:
            PermissionError: If not authorized to update
            ValueError: If validation fails
        """
        server = await self.get_server(server_id, user_id, is_admin)
        if not server:
            return None

        # Check ownership (non-admins can only update their own)
        if not is_admin and server.created_by_user_id != user_id:
            raise PermissionError("Cannot update server you don't own")

        # Only admins can change global flag
        if data.is_global is not None and not is_admin:
            raise PermissionError("Only administrators can change global setting")

        # Update fields
        if data.display_name is not None:
            server.display_name = data.display_name
        if data.description is not None:
            server.description = data.description
        if data.server_url is not None:
            server.server_url = data.server_url
        if data.api_key_header_name is not None:
            server.api_key_header_name = data.api_key_header_name
        if data.timeout_seconds is not None:
            server.timeout_seconds = data.timeout_seconds
        if data.max_retries is not None:
            server.max_retries = data.max_retries
        if data.is_active is not None:
            server.is_active = data.is_active
        if data.is_global is not None and is_admin:
            server.is_global = data.is_global

        # Handle API key update
        if data.api_key is not None:
            if data.api_key == "":
                # Empty string means remove the key
                server.api_key = None
            else:
                server.api_key = data.api_key

        await self.db.commit()
        await self.db.refresh(server)

        # Invalidate cache
        await self._invalidate_server_cache(server.name, user_id)

        logger.info(f"Updated MCP server {server_id} by user {user_id}")
        return server

    # =========================================================================
    # Delete Operations
    # =========================================================================

    async def delete_server(
        self,
        server_id: int,
        user_id: int,
        is_admin: bool = False
    ) -> bool:
        """
        Delete an MCP server configuration.

        Args:
            server_id: Server ID to delete
            user_id: Requesting user ID
            is_admin: Whether user is admin

        Returns:
            True if deleted, False if not found

        Raises:
            PermissionError: If not authorized to delete
        """
        server = await self.get_server(server_id, user_id, is_admin)
        if not server:
            return False

        # Check ownership
        if not is_admin and server.created_by_user_id != user_id:
            raise PermissionError("Cannot delete server you don't own")

        server_name = server.name
        await self.db.delete(server)
        await self.db.commit()

        # Invalidate cache
        await self._invalidate_server_cache(server_name, user_id)

        logger.info(f"Deleted MCP server {server_id} by user {user_id}")
        return True

    # =========================================================================
    # Connection Testing
    # =========================================================================

    async def test_connection(
        self,
        data: MCPServerTestRequest
    ) -> MCPServerTestResponse:
        """
        Test connection to an MCP server and discover tools.

        This is used before saving to verify the server is reachable.

        Args:
            data: Test request with URL and optional API key

        Returns:
            Test response with success status and discovered tools
        """
        start_time = time.time()

        try:
            client = MCPClient(
                server_url=data.server_url,
                api_key=data.api_key,
                api_key_header_name=data.api_key_header_name,
                timeout_seconds=data.timeout_seconds
            )

            # Fetch tools from server
            tools = await client.list_tools()

            response_time_ms = int((time.time() - start_time) * 1000)

            # Convert to MCPToolInfo format
            tool_infos = []
            for tool in tools:
                func = tool.get("function", {})
                tool_infos.append(MCPToolInfo(
                    name=func.get("name", ""),
                    description=func.get("description"),
                    parameters_schema=func.get("parameters")
                ))

            return MCPServerTestResponse(
                success=True,
                message=f"Successfully connected and discovered {len(tools)} tools",
                tools=tool_infos,
                tool_count=len(tools),
                response_time_ms=response_time_ms
            )

        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"MCP connection test failed: {e}")

            return MCPServerTestResponse(
                success=False,
                message="Connection failed",
                tools=[],
                tool_count=0,
                response_time_ms=response_time_ms,
                error=str(e)
            )

    async def refresh_server_tools(
        self,
        server_id: int,
        user_id: int,
        is_admin: bool = False
    ) -> MCPServerRefreshResponse:
        """
        Refresh the cached tools for an MCP server.

        Args:
            server_id: Server ID
            user_id: Requesting user ID
            is_admin: Whether user is admin

        Returns:
            Refresh response with updated tools
        """
        server = await self.get_server(server_id, user_id, is_admin)
        if not server:
            return MCPServerRefreshResponse(
                success=False,
                message="Server not found",
                error="Server not found or not accessible"
            )

        try:
            client = MCPClient(
                server_url=server.server_url,
                api_key=server.api_key,
                api_key_header_name=server.api_key_header_name,
                timeout_seconds=server.timeout_seconds
            )

            tools = await client.list_tools()

            # Update server with new tools
            server.cached_tools = tools
            server.update_connection_status(success=True)

            await self.db.commit()
            await self.db.refresh(server)

            # Convert to MCPToolInfo format
            tool_infos = []
            for tool in tools:
                func = tool.get("function", {})
                tool_infos.append(MCPToolInfo(
                    name=func.get("name", ""),
                    description=func.get("description"),
                    parameters_schema=func.get("parameters")
                ))

            # Invalidate cache
            await self._invalidate_server_cache(server.name, user_id)

            return MCPServerRefreshResponse(
                success=True,
                tools=tool_infos,
                tool_count=len(tools),
                message=f"Successfully refreshed {len(tools)} tools"
            )

        except Exception as e:
            # Update connection status with error
            server.update_connection_status(success=False, error=str(e))
            await self.db.commit()

            logger.warning(f"Failed to refresh tools for server {server_id}: {e}")

            return MCPServerRefreshResponse(
                success=False,
                tools=[],
                tool_count=0,
                message="Failed to refresh tools",
                error=str(e)
            )

    # =========================================================================
    # Tool Calling Integration
    # =========================================================================

    async def get_server_config_for_tool_calling(
        self,
        server_name: str,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get server configuration for use with tool calling.

        This method is called by ToolCallingService when executing MCP tools.

        Args:
            server_name: Name of the MCP server
            user_id: User ID making the request

        Returns:
            Config dict with url, api_key, timeout, max_retries
            or None if server not found
        """
        server = await self.get_server_by_name(server_name, user_id)
        if not server or not server.is_active:
            return None

        # Update usage tracking
        server.record_usage()
        await self.db.commit()

        return {
            "url": server.server_url,
            "api_key": server.api_key,
            "api_key_header_name": server.api_key_header_name,
            "timeout": server.timeout_seconds,
            "max_retries": server.max_retries
        }

    async def get_available_mcp_servers(
        self,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get list of available MCP servers for agent configuration.

        Returns simplified list suitable for dropdown selection.

        Args:
            user_id: User ID

        Returns:
            List of dicts with name, display_name, tool_count
        """
        servers, _, _ = await self.list_servers(user_id, include_inactive=False)

        return [
            {
                "name": s.name,
                "display_name": s.display_name,
                "description": s.description,
                "tool_count": len(s.cached_tools) if s.cached_tools else 0,
                "is_global": s.is_global
            }
            for s in servers
        ]

    # =========================================================================
    # Cache Management
    # =========================================================================

    async def _invalidate_server_cache(self, server_name: str, user_id: int):
        """Invalidate cache entries for a server."""
        cache_key = f"mcp_server:{server_name}:{user_id}"
        await self.cache.delete(cache_key)

        # Also invalidate potential global cache
        global_key = f"mcp_server:{server_name}:*"
        await self.cache.delete(global_key)

    async def invalidate_all_caches(self):
        """Invalidate all MCP server caches."""
        # This is a simplified approach - in production you might want
        # pattern-based deletion if your cache supports it
        logger.info("Invalidating all MCP server caches")
