"""
Tool Execution Service with Docker Sandboxing
Secure execution environment for user-defined tools
"""
import asyncio
import json
import logging
import os
import tempfile
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import docker
from docker.errors import DockerException, ContainerError, ImageNotFound
import psutil

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from app.models.tool import Tool, ToolExecution, ToolStatus, ToolType
from app.models.user import User
from app.core.config import settings

logger = logging.getLogger(__name__)


class ToolExecutionService:
    """Service for secure tool execution with Docker sandboxing"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.docker_client = None
        self._init_docker()

    def _init_docker(self):
        """Initialize Docker client"""
        try:
            self.docker_client = docker.from_env()
            # Test Docker connection
            self.docker_client.ping()
            logger.info("Docker client initialized successfully")
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.docker_client = None

    async def execute_tool(
        self,
        tool_id: int,
        user_id: int,
        parameters: Dict[str, Any],
        timeout_override: Optional[int] = None,
    ) -> ToolExecution:
        """Execute a tool with the given parameters"""

        # Get tool and validate access
        tool = await self._get_tool_and_validate_access(tool_id, user_id)

        # Create execution record
        execution = ToolExecution(
            tool_id=tool_id,
            executed_by_user_id=user_id,
            parameters=parameters,
            status=ToolStatus.PENDING,
        )

        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)

        try:
            # Update status to running
            execution.status = ToolStatus.RUNNING
            execution.started_at = datetime.utcnow()
            await self.db.commit()

            # Execute based on tool type
            if tool.tool_type == ToolType.DOCKER:
                await self._execute_docker_tool(
                    execution, tool, parameters, timeout_override
                )
            elif tool.tool_type == ToolType.PYTHON:
                await self._execute_python_tool(
                    execution, tool, parameters, timeout_override
                )
            elif tool.tool_type == ToolType.BASH:
                await self._execute_bash_tool(
                    execution, tool, parameters, timeout_override
                )
            else:
                raise ValueError(f"Unsupported tool type: {tool.tool_type}")

            # Update tool usage
            tool.increment_usage()
            await self.db.commit()

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            execution.status = ToolStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            await self.db.commit()

        await self.db.refresh(execution)
        return execution

    async def _get_tool_and_validate_access(self, tool_id: int, user_id: int) -> Tool:
        """Get tool and validate user access"""
        stmt = select(Tool).where(Tool.id == tool_id)
        result = await self.db.execute(stmt)
        tool = result.scalar_one_or_none()

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found"
            )

        if not tool.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Tool is not active"
            )

        # Get user for permission check
        user_stmt = select(User).where(User.id == user_id)
        user_result = await self.db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user or not tool.can_be_used_by(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this tool",
            )

        return tool

    async def _execute_docker_tool(
        self,
        execution: ToolExecution,
        tool: Tool,
        parameters: Dict[str, Any],
        timeout_override: Optional[int] = None,
    ):
        """Execute tool in Docker container"""
        if not self.docker_client:
            raise RuntimeError("Docker is not available")

        timeout = timeout_override or tool.timeout_seconds
        memory_limit = f"{tool.max_memory_mb}m"

        # Prepare execution environment
        env_vars = {"TOOL_PARAMETERS": json.dumps(parameters), "PYTHONUNBUFFERED": "1"}

        # Create temporary directory for code
        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = os.path.join(temp_dir, "tool_code.py")
            with open(code_file, "w") as f:
                f.write(tool.code)

            container = None
            try:
                # Run container
                container = self.docker_client.containers.run(
                    image=tool.docker_image or "python:3.11-slim",
                    command=tool.docker_command or ["python", "/app/tool_code.py"],
                    environment=env_vars,
                    volumes={temp_dir: {"bind": "/app", "mode": "ro"}},
                    mem_limit=memory_limit,
                    cpu_quota=int(
                        tool.max_cpu_seconds * 100000
                    ),  # Convert to microseconds
                    cpu_period=100000,
                    network_disabled=True,  # No network access for security
                    detach=True,
                    remove=False,  # Keep container for log retrieval
                    working_dir="/app",
                )

                execution.container_id = container.id
                await self.db.commit()

                # Wait for completion with timeout
                try:
                    result = container.wait(timeout=timeout)
                    execution.return_code = result["StatusCode"]
                except asyncio.TimeoutError:
                    container.kill()
                    execution.status = ToolStatus.TIMEOUT
                    execution.error_message = (
                        f"Tool execution timed out after {timeout} seconds"
                    )
                    execution.completed_at = datetime.utcnow()
                    return

                # Get output and logs
                try:
                    output = container.logs(stdout=True, stderr=False).decode("utf-8")
                    error_logs = container.logs(stdout=False, stderr=True).decode(
                        "utf-8"
                    )

                    execution.output = output
                    execution.docker_logs = error_logs

                    if execution.return_code == 0:
                        execution.status = ToolStatus.COMPLETED
                    else:
                        execution.status = ToolStatus.FAILED
                        execution.error_message = error_logs or "Tool execution failed"

                except Exception as e:
                    logger.error(f"Failed to retrieve container output: {e}")
                    execution.error_message = f"Failed to retrieve output: {e}"
                    execution.status = ToolStatus.FAILED

                # Get resource usage stats
                try:
                    stats = container.stats(stream=False)
                    memory_usage = stats["memory_stats"].get("usage", 0)
                    execution.memory_used_mb = memory_usage / (
                        1024 * 1024
                    )  # Convert to MB
                except Exception as e:
                    logger.warning(f"Failed to get container stats: {e}")

            except ContainerError as e:
                execution.status = ToolStatus.FAILED
                execution.error_message = f"Container execution failed: {e}"
                execution.return_code = e.exit_status

            except ImageNotFound:
                execution.status = ToolStatus.FAILED
                execution.error_message = f"Docker image not found: {tool.docker_image}"

            except Exception as e:
                execution.status = ToolStatus.FAILED
                execution.error_message = f"Unexpected error: {e}"

            finally:
                # Cleanup container
                if container:
                    try:
                        container.remove(force=True)
                    except Exception as e:
                        logger.warning(f"Failed to remove container: {e}")

                execution.completed_at = datetime.utcnow()
                if execution.started_at:
                    duration = execution.completed_at - execution.started_at
                    execution.execution_time_ms = int(duration.total_seconds() * 1000)

                await self.db.commit()

    async def _execute_python_tool(
        self,
        execution: ToolExecution,
        tool: Tool,
        parameters: Dict[str, Any],
        timeout_override: Optional[int] = None,
    ):
        """Execute Python tool in Docker container for security"""
        # Use Docker for Python execution too for security
        docker_tool = Tool(
            id=tool.id,
            name=tool.name,
            display_name=tool.display_name,
            description=tool.description,
            tool_type=ToolType.DOCKER,
            code=tool.code,
            parameters_schema=tool.parameters_schema,
            return_schema=tool.return_schema,
            timeout_seconds=tool.timeout_seconds,
            max_memory_mb=tool.max_memory_mb,
            max_cpu_seconds=tool.max_cpu_seconds,
            docker_image="python:3.11-slim",
            docker_command=["python", "/app/tool_code.py"],
            is_public=tool.is_public,
            is_approved=tool.is_approved,
            created_by_user_id=tool.created_by_user_id,
        )

        await self._execute_docker_tool(
            execution, docker_tool, parameters, timeout_override
        )

    async def _execute_bash_tool(
        self,
        execution: ToolExecution,
        tool: Tool,
        parameters: Dict[str, Any],
        timeout_override: Optional[int] = None,
    ):
        """Execute Bash tool in Docker container for security"""
        # Wrap bash script for Docker execution
        bash_wrapper = f"""#!/bin/bash
set -e
export TOOL_PARAMETERS='{json.dumps(parameters)}'

{tool.code}
"""

        docker_tool = Tool(
            id=tool.id,
            name=tool.name,
            display_name=tool.display_name,
            description=tool.description,
            tool_type=ToolType.DOCKER,
            code=bash_wrapper,
            parameters_schema=tool.parameters_schema,
            return_schema=tool.return_schema,
            timeout_seconds=tool.timeout_seconds,
            max_memory_mb=tool.max_memory_mb,
            max_cpu_seconds=tool.max_cpu_seconds,
            docker_image="ubuntu:20.04",
            docker_command=["bash", "/app/tool_code.py"],
            is_public=tool.is_public,
            is_approved=tool.is_approved,
            created_by_user_id=tool.created_by_user_id,
        )

        await self._execute_docker_tool(
            execution, docker_tool, parameters, timeout_override
        )

    async def cancel_execution(self, execution_id: int, user_id: int) -> ToolExecution:
        """Cancel a running tool execution"""
        stmt = select(ToolExecution).where(ToolExecution.id == execution_id)
        result = await self.db.execute(stmt)
        execution = result.scalar_one_or_none()

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found"
            )

        # Check permission (only creator or admin can cancel)
        if execution.executed_by_user_id != user_id:
            user_stmt = select(User).where(User.id == user_id)
            user_result = await self.db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if not user or not user.has_permission("manage_tools"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
                )

        if not execution.is_running():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Execution is not running",
            )

        # Kill container if it exists
        if execution.container_id and self.docker_client:
            try:
                container = self.docker_client.containers.get(execution.container_id)
                container.kill()
                container.remove(force=True)
                logger.info(f"Killed container {execution.container_id}")
            except Exception as e:
                logger.warning(f"Failed to kill container: {e}")

        # Update execution status
        execution.status = ToolStatus.CANCELLED
        execution.completed_at = datetime.utcnow()
        execution.error_message = "Execution cancelled by user"

        await self.db.commit()
        await self.db.refresh(execution)

        return execution

    async def get_execution_logs(
        self, execution_id: int, user_id: int
    ) -> Dict[str, Any]:
        """Get real-time logs for a running execution"""
        stmt = select(ToolExecution).where(ToolExecution.id == execution_id)
        result = await self.db.execute(stmt)
        execution = result.scalar_one_or_none()

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found"
            )

        # Check permission
        if execution.executed_by_user_id != user_id:
            user_stmt = select(User).where(User.id == user_id)
            user_result = await self.db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if not user or not user.has_permission("manage_tools"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
                )

        logs = {
            "execution_id": execution_id,
            "status": execution.status,
            "output": execution.output or "",
            "error_message": execution.error_message or "",
            "docker_logs": execution.docker_logs or "",
            "is_running": execution.is_running(),
        }

        # Get live logs if container is running
        if execution.container_id and execution.is_running() and self.docker_client:
            try:
                container = self.docker_client.containers.get(execution.container_id)
                live_logs = container.logs(
                    stdout=True, stderr=True, stream=False, tail=100
                ).decode("utf-8")
                logs["live_logs"] = live_logs
            except Exception as e:
                logger.warning(f"Failed to get live logs: {e}")
                logs["live_logs"] = ""

        return logs

    async def cleanup_old_executions(self, days_old: int = 30):
        """Clean up old execution records and containers"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        # Get old executions
        stmt = select(ToolExecution).where(
            ToolExecution.created_at < cutoff_date,
            ToolExecution.status.in_(
                [ToolStatus.COMPLETED, ToolStatus.FAILED, ToolStatus.CANCELLED]
            ),
        )
        result = await self.db.execute(stmt)
        old_executions = result.scalars().all()

        cleaned_count = 0
        for execution in old_executions:
            # Clean up any remaining containers
            if execution.container_id and self.docker_client:
                try:
                    container = self.docker_client.containers.get(
                        execution.container_id
                    )
                    container.remove(force=True)
                    logger.debug(f"Removed old container {execution.container_id}")
                except Exception:
                    pass  # Container probably already gone

            # Delete execution record
            await self.db.delete(execution)
            cleaned_count += 1

        await self.db.commit()
        logger.info(f"Cleaned up {cleaned_count} old tool executions")

        return cleaned_count
