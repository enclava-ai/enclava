"""Workflow service facade for scaffolded workflow capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.schemas.workflow import (
    WorkflowDefinitionDocument,
    WorkflowStepCatalogEntry,
    WorkflowTemplate,
)

from .registry import StepRegistry, create_default_step_registry
from .templates import get_workflow_template, list_workflow_templates


@dataclass
class WorkflowRuntimeDependencies:
    """Optional runtime dependencies used by future workflow execution phases."""

    agent_service: Optional[Any] = None
    rag_service: Optional[Any] = None
    extract_service: Optional[Any] = None
    connector_service: Optional[Any] = None
    notification_service: Optional[Any] = None
    audit_service: Optional[Any] = None
    budget_service: Optional[Any] = None


class WorkflowService:
    """Facade for workflow contract validation and catalog lookup."""

    def __init__(
        self,
        dependencies: Optional[WorkflowRuntimeDependencies] = None,
        step_registry: Optional[StepRegistry] = None,
    ) -> None:
        self.dependencies = dependencies or WorkflowRuntimeDependencies()
        self.step_registry = step_registry or create_default_step_registry()

    def validate_definition(
        self, definition: WorkflowDefinitionDocument | dict[str, Any]
    ) -> WorkflowDefinitionDocument:
        """Validate and normalize a workflow definition document."""
        if isinstance(definition, WorkflowDefinitionDocument):
            return definition.model_copy(deep=True)

        return WorkflowDefinitionDocument.model_validate(definition)

    def list_step_catalog(self) -> list[WorkflowStepCatalogEntry]:
        """Return workflow step catalog entries."""
        return self.step_registry.list()

    def get_step_catalog(self, step_type: str) -> WorkflowStepCatalogEntry:
        """Return a single workflow step catalog entry."""
        return self.step_registry.require(step_type)

    def list_templates(self) -> list[WorkflowTemplate]:
        """Return available workflow template seeds."""
        return list_workflow_templates()

    def get_template(self, template_id: str) -> WorkflowTemplate:
        """Return a workflow template seed by id."""
        return get_workflow_template(template_id)
