"""
Code Execution Built-in Tool

Executes Python code in a secure sandbox environment.
"""

from typing import Dict, Any
from .base import BuiltinTool, ToolExecutionContext, ToolResult
from app.models.tool import Tool, ToolType, ToolStatus


class CodeExecutionTool(BuiltinTool):
    """Built-in tool for executing Python code in a secure sandbox.

    This tool creates ephemeral Tool records and executes them using
    the existing ToolExecutionService Docker sandbox infrastructure.

    IMPORTANT: Uses ToolStatus.COMPLETED enum (not string comparison)
    for status checking.

    Attributes:
        name: "code_execution" - unique identifier for the tool
        display_name: "Code Execution" - human-readable name
        description: Description for the LLM to understand when to use this tool
        parameters_schema: JSON Schema for the code and timeout parameters
    """

    name = "code_execution"
    display_name = "Code Execution"  # Required by _convert_tools_to_openai_format
    description = "Execute Python code in a secure sandbox environment"
    parameters_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Execution timeout in seconds (default: 30)",
                "default": 30,
                "minimum": 1,
                "maximum": 300
            }
        },
        "required": ["code"]
    }

    async def execute(self, params: Dict[str, Any], ctx: ToolExecutionContext) -> ToolResult:
        """Execute Python code in a secure sandbox.

        Creates an ephemeral Tool record, executes it using ToolExecutionService,
        and cleans up the ephemeral record after execution.

        Args:
            params: Dictionary containing:
                - code (str): Python code to execute
                - timeout (int, optional): Timeout in seconds (default: 30)
            ctx: Execution context with user_id and db session

        Returns:
            ToolResult with execution output or error
        """
        from app.services.tool_execution_service import ToolExecutionService

        try:
            # Extract parameters
            code = params.get("code")
            if not code:
                return ToolResult(
                    success=False,
                    output=None,
                    error="Code parameter is required"
                )

            timeout = params.get("timeout", 30)

            # Validate timeout
            if timeout < 1 or timeout > 300:
                return ToolResult(
                    success=False,
                    output=None,
                    error="Timeout must be between 1 and 300 seconds"
                )

            # Create ephemeral tool record for execution
            # This tool will be deleted after execution
            ephemeral_tool = Tool(
                name=f"_ephemeral_code_{ctx.user_id}",
                display_name="Code Execution",
                description="Ephemeral code execution",
                tool_type=ToolType.PYTHON,
                code=code,
                parameters_schema={"type": "object", "properties": {}},
                timeout_seconds=timeout,
                max_memory_mb=256,
                max_cpu_seconds=timeout,
                is_public=False,
                is_approved=True,  # Built-in tools are pre-approved
                created_by_user_id=ctx.user_id,
                is_active=True,
            )

            # Add to session temporarily and flush to get ID
            ctx.db.add(ephemeral_tool)
            await ctx.db.flush()  # Get ID without committing

            try:
                # Execute using existing ToolExecutionService infrastructure
                exec_service = ToolExecutionService(ctx.db)
                execution = await exec_service.execute_tool(
                    tool_id=ephemeral_tool.id,
                    user_id=ctx.user_id,
                    parameters={},  # Code is in the tool itself
                    timeout_override=timeout
                )

                # IMPORTANT: Use ToolStatus enum, NOT string comparison
                # execution.status is a ToolStatus enum value, not a string
                success = (execution.status == ToolStatus.COMPLETED)

                return ToolResult(
                    success=success,
                    output={
                        "stdout": execution.output,
                        "stderr": execution.error_message if not success else None,
                        "status": execution.status.value,
                        "execution_time": execution.execution_time_seconds
                    },
                    error=execution.error_message if not success else None
                )

            finally:
                # Clean up ephemeral tool
                # This ensures the temporary tool is removed even if execution fails
                await ctx.db.delete(ephemeral_tool)
                await ctx.db.flush()

        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Code execution failed: {str(e)}"
            )
