"""Workflow module implementation."""

import time
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.core.logging import get_logger
from app.services.base_module import BaseModule, Permission
from app.services.workflows import WorkflowRuntimeDependencies, WorkflowService

from ..protocols import AgentServiceProtocol

logger = get_logger(__name__)


class WorkflowModule(BaseModule):
    """Coordinates simple workflow execution across platform modules."""

    version = "1.0.0"
    description = "Workflow orchestration for module-based automations"

    def __init__(
        self,
        agent_service: Optional[AgentServiceProtocol] = None,
        workflow_service: Optional[WorkflowService] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(module_id="workflow", config=config)
        self.agent_service = agent_service
        self.workflow_service = workflow_service or WorkflowService(
            dependencies=WorkflowRuntimeDependencies(agent_service=agent_service)
        )
        self.started_at: Optional[float] = None
        self.executions_started = 0
        self.executions_completed = 0

    async def initialize(self):
        """Initialize workflow orchestration."""
        self.started_at = time.time()
        self.initialized = True
        logger.info("Workflow module initialized")
        return True

    async def cleanup(self):
        """Cleanup workflow resources."""
        self.initialized = False
        logger.info("Workflow module cleanup completed")

    def get_required_permissions(self) -> List[Permission]:
        """Return workflow permissions."""
        return [
            Permission("workflow", "execute", "Execute workflows"),
            Permission("workflow", "read", "Read workflow definitions"),
            Permission("workflow", "manage", "Manage workflow definitions"),
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Return workflow module statistics."""
        uptime = time.time() - self.started_at if self.started_at else 0.0
        return {
            "executions_started": self.executions_started,
            "executions_completed": self.executions_completed,
            "active_executions": self.executions_started - self.executions_completed,
            "registered_step_types": len(self.workflow_service.list_step_catalog()),
            "template_count": len(self.workflow_service.list_templates()),
            "uptime_seconds": uptime,
        }

    async def process_request(
        self, request: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a workflow request."""
        action = request.get("action", "status")

        if action == "status":
            stats = self.get_stats()
            db_session = context.get("db_session") or context.get("db")
            if db_session is not None:
                stats["persisted_workflow_count"] = (
                    await self.workflow_service.count_definitions(db_session)
                )
            return {"success": True, "stats": stats}

        if action == "catalog":
            return {
                "success": True,
                "steps": [
                    step.model_dump()
                    for step in self.workflow_service.list_step_catalog()
                ],
            }

        if action == "templates":
            return {
                "success": True,
                "templates": [
                    template.model_dump(mode="json")
                    for template in self.workflow_service.list_templates()
                ],
            }

        if action == "validate":
            try:
                definition = self.workflow_service.validate_definition(
                    request.get("definition", {})
                )
            except ValidationError as exc:
                return {"success": False, "error": str(exc), "details": exc.errors()}

            return {"success": True, "definition": definition.model_dump(mode="json")}

        if action == "execute":
            self.executions_started += 1
            try:
                workflow = request.get("workflow", {})
                return {
                    "success": True,
                    "workflow": workflow,
                    "context": context,
                    "status": "completed",
                }
            finally:
                self.executions_completed += 1

        return {"success": False, "error": f"Unknown workflow action: {action}"}


def create_module(
    agent_service: Optional[AgentServiceProtocol] = None,
    workflow_service: Optional[WorkflowService] = None,
    config: Optional[Dict[str, Any]] = None,
) -> WorkflowModule:
    """Factory function for dependency injection."""
    return WorkflowModule(
        agent_service=agent_service,
        workflow_service=workflow_service,
        config=config,
    )


workflow_module = WorkflowModule()
