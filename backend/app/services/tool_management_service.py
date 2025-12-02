"""
Tool Management Service
Service for managing custom tools and their lifecycle
"""
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, desc, func
from fastapi import HTTPException, status
from datetime import datetime, timedelta

from app.models.tool import Tool, ToolExecution, ToolCategory, ToolType, ToolStatus
from app.models.user import User

logger = logging.getLogger(__name__)


class ToolManagementService:
    """Service for managing tools and categories"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tool(
        self,
        name: str,
        display_name: str,
        code: str,
        tool_type: str,
        created_by_user_id: int,
        description: Optional[str] = None,
        parameters_schema: Optional[Dict[str, Any]] = None,
        return_schema: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 30,
        max_memory_mb: int = 256,
        max_cpu_seconds: float = 10.0,
        docker_image: Optional[str] = None,
        docker_command: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: bool = False,
    ) -> Tool:
        """Create a new tool"""

        # Validate tool type
        if tool_type not in [t.value for t in ToolType]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tool type: {tool_type}",
            )

        # Check if tool name is unique for user
        existing_tool = await self.get_tool_by_name_and_user(name, created_by_user_id)
        if existing_tool:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tool with this name already exists",
            )

        # Validate Docker settings
        if tool_type == ToolType.DOCKER and not docker_image:
            docker_image = "python:3.11-slim"  # Default image

        # Create tool
        tool = Tool(
            name=name,
            display_name=display_name,
            description=description,
            tool_type=tool_type,
            code=code,
            parameters_schema=parameters_schema or {},
            return_schema=return_schema or {},
            timeout_seconds=min(timeout_seconds, 300),  # Max 5 minutes
            max_memory_mb=min(max_memory_mb, 1024),  # Max 1GB
            max_cpu_seconds=min(max_cpu_seconds, 60.0),  # Max 60 seconds
            docker_image=docker_image,
            docker_command=docker_command,
            is_public=is_public,
            is_approved=False,  # Requires admin approval for public tools
            created_by_user_id=created_by_user_id,
            category=category,
            tags=tags or [],
        )

        self.db.add(tool)
        await self.db.commit()
        await self.db.refresh(tool)

        logger.info(f"Created tool '{name}' by user {created_by_user_id}")
        return tool

    async def get_tool_by_id(self, tool_id: int) -> Optional[Tool]:
        """Get tool by ID"""
        stmt = select(Tool).where(Tool.id == tool_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_tool_by_name_and_user(
        self, name: str, user_id: int
    ) -> Optional[Tool]:
        """Get tool by name and user"""
        stmt = select(Tool).where(
            and_(Tool.name == name, Tool.created_by_user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_tools(
        self,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        tool_type: Optional[str] = None,
        is_public: Optional[bool] = None,
        is_approved: Optional[bool] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by_user_id: Optional[int] = None,
    ) -> List[Tool]:
        """Get tools with filtering and pagination"""

        query = select(Tool)

        # Apply filters
        conditions = []

        if user_id:
            # User can see their own tools, public approved tools, or if they have manage_tools permission
            user_stmt = select(User).where(User.id == user_id)
            user_result = await self.db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if user and user.has_permission("manage_tools"):
                # Admins can see all tools
                pass
            else:
                # Regular users can see their own tools + public approved tools
                conditions.append(
                    or_(
                        Tool.created_by_user_id == user_id,
                        and_(Tool.is_public == True, Tool.is_approved == True),
                    )
                )

        if category:
            conditions.append(Tool.category == category)

        if tool_type:
            conditions.append(Tool.tool_type == tool_type)

        if is_public is not None:
            conditions.append(Tool.is_public == is_public)

        if is_approved is not None:
            conditions.append(Tool.is_approved == is_approved)

        if created_by_user_id:
            conditions.append(Tool.created_by_user_id == created_by_user_id)

        if search:
            search_term = f"%{search}%"
            conditions.append(
                or_(
                    Tool.name.ilike(search_term),
                    Tool.display_name.ilike(search_term),
                    Tool.description.ilike(search_term),
                )
            )

        if tags:
            # Check if any of the provided tags exist in the tool's tags
            for tag in tags:
                conditions.append(Tool.tags.contains([tag]))

        if conditions:
            query = query.where(and_(*conditions))

        # Order by usage count and creation date
        query = query.order_by(desc(Tool.usage_count), desc(Tool.created_at))
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_tool(
        self,
        tool_id: int,
        user_id: int,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        code: Optional[str] = None,
        parameters_schema: Optional[Dict[str, Any]] = None,
        return_schema: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[int] = None,
        max_memory_mb: Optional[int] = None,
        max_cpu_seconds: Optional[float] = None,
        docker_image: Optional[str] = None,
        docker_command: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> Tool:
        """Update tool (only by creator or admin)"""

        tool = await self.get_tool_by_id(tool_id)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found"
            )

        # Check permission
        user_stmt = select(User).where(User.id == user_id)
        user_result = await self.db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if tool.created_by_user_id != user_id and not user.has_permission(
            "manage_tools"
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Update fields
        if display_name is not None:
            tool.display_name = display_name

        if description is not None:
            tool.description = description

        if code is not None:
            tool.code = code
            # Reset approval status if code changes
            if tool.is_public:
                tool.is_approved = False

        if parameters_schema is not None:
            tool.parameters_schema = parameters_schema

        if return_schema is not None:
            tool.return_schema = return_schema

        if timeout_seconds is not None:
            tool.timeout_seconds = min(timeout_seconds, 300)

        if max_memory_mb is not None:
            tool.max_memory_mb = min(max_memory_mb, 1024)

        if max_cpu_seconds is not None:
            tool.max_cpu_seconds = min(max_cpu_seconds, 60.0)

        if docker_image is not None:
            tool.docker_image = docker_image

        if docker_command is not None:
            tool.docker_command = docker_command

        if category is not None:
            tool.category = category

        if tags is not None:
            tool.tags = tags

        if is_public is not None:
            tool.is_public = is_public
            # Reset approval if making public
            if is_public and not tool.is_approved:
                tool.is_approved = False

        if is_active is not None:
            tool.is_active = is_active

        tool.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(tool)

        logger.info(f"Updated tool {tool_id} by user {user_id}")
        return tool

    async def delete_tool(self, tool_id: int, user_id: int) -> bool:
        """Delete tool (only by creator or admin)"""

        tool = await self.get_tool_by_id(tool_id)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found"
            )

        # Check permission
        user_stmt = select(User).where(User.id == user_id)
        user_result = await self.db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if tool.created_by_user_id != user_id and not user.has_permission(
            "manage_tools"
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Check if tool has running executions
        running_executions = await self.db.execute(
            select(func.count(ToolExecution.id)).where(
                and_(
                    ToolExecution.tool_id == tool_id,
                    ToolExecution.status.in_([ToolStatus.PENDING, ToolStatus.RUNNING]),
                )
            )
        )

        if running_executions.scalar() > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete tool with running executions",
            )

        await self.db.delete(tool)
        await self.db.commit()

        logger.info(f"Deleted tool {tool_id} by user {user_id}")
        return True

    async def approve_tool(self, tool_id: int, admin_user_id: int) -> Tool:
        """Approve tool for public use (admin only)"""

        tool = await self.get_tool_by_id(tool_id)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found"
            )

        # Check admin permission
        user_stmt = select(User).where(User.id == admin_user_id)
        user_result = await self.db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user or not user.has_permission("manage_tools"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )

        tool.is_approved = True
        tool.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(tool)

        logger.info(f"Tool {tool_id} approved by admin {admin_user_id}")
        return tool

    async def get_tool_executions(
        self,
        tool_id: Optional[int] = None,
        user_id: Optional[int] = None,
        executed_by_user_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ToolExecution]:
        """Get tool executions with filtering"""

        query = select(ToolExecution)

        conditions = []

        if tool_id:
            conditions.append(ToolExecution.tool_id == tool_id)

        if executed_by_user_id:
            conditions.append(ToolExecution.executed_by_user_id == executed_by_user_id)

        if status:
            conditions.append(ToolExecution.status == status)

        # Permission check - users can only see their own executions unless admin
        if user_id:
            user_stmt = select(User).where(User.id == user_id)
            user_result = await self.db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if user and not user.has_permission("manage_tools"):
                conditions.append(ToolExecution.executed_by_user_id == user_id)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(desc(ToolExecution.created_at))
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_tool_statistics(
        self, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get tool usage statistics"""

        stats = {}

        # Total tools
        total_tools = await self.db.execute(select(func.count(Tool.id)))
        stats["total_tools"] = total_tools.scalar()

        # Public tools
        public_tools = await self.db.execute(
            select(func.count(Tool.id)).where(Tool.is_public == True)
        )
        stats["public_tools"] = public_tools.scalar()

        # Tools by type
        tools_by_type = await self.db.execute(
            select(Tool.tool_type, func.count(Tool.id)).group_by(Tool.tool_type)
        )
        stats["tools_by_type"] = dict(tools_by_type.all())

        # Total executions
        total_executions = await self.db.execute(select(func.count(ToolExecution.id)))
        stats["total_executions"] = total_executions.scalar()

        # Executions by status
        executions_by_status = await self.db.execute(
            select(ToolExecution.status, func.count(ToolExecution.id)).group_by(
                ToolExecution.status
            )
        )
        stats["executions_by_status"] = dict(executions_by_status.all())

        # Recent executions (last 24h)
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        recent_executions = await self.db.execute(
            select(func.count(ToolExecution.id)).where(
                ToolExecution.created_at >= twenty_four_hours_ago
            )
        )
        stats["recent_executions"] = recent_executions.scalar()

        # Top tools by usage
        top_tools = await self.db.execute(
            select(Tool.name, Tool.usage_count)
            .order_by(desc(Tool.usage_count))
            .limit(10)
        )
        stats["top_tools"] = [
            {"name": name, "usage_count": count} for name, count in top_tools.all()
        ]

        # User-specific stats
        if user_id:
            user_tools = await self.db.execute(
                select(func.count(Tool.id)).where(Tool.created_by_user_id == user_id)
            )
            stats["user_tools"] = user_tools.scalar()

            user_executions = await self.db.execute(
                select(func.count(ToolExecution.id)).where(
                    ToolExecution.executed_by_user_id == user_id
                )
            )
            stats["user_executions"] = user_executions.scalar()

        return stats

    # Category Management

    async def create_category(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        color: Optional[str] = None,
        sort_order: int = 0,
    ) -> ToolCategory:
        """Create a new tool category"""

        # Check if category name exists
        existing = await self.db.execute(
            select(ToolCategory).where(ToolCategory.name == name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category with this name already exists",
            )

        category = ToolCategory(
            name=name,
            display_name=display_name,
            description=description,
            icon=icon,
            color=color,
            sort_order=sort_order,
        )

        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)

        return category

    async def get_categories(self) -> List[ToolCategory]:
        """Get all active categories"""
        stmt = (
            select(ToolCategory)
            .where(ToolCategory.is_active == True)
            .order_by(ToolCategory.sort_order)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
