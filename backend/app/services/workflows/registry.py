"""Workflow step registry scaffolding."""

from __future__ import annotations

from typing import Iterable, Optional

from app.schemas.workflow import WorkflowStepCatalogEntry


class StepRegistry:
    """Registry of workflow step capabilities available to builders."""

    def __init__(
        self, entries: Optional[Iterable[WorkflowStepCatalogEntry]] = None
    ) -> None:
        self._entries: dict[str, WorkflowStepCatalogEntry] = {}

        for entry in entries or []:
            self.register(entry)

    def register(self, entry: WorkflowStepCatalogEntry) -> None:
        """Register or replace a step catalog entry."""
        self._entries[entry.type] = entry

    def get(self, step_type: str) -> Optional[WorkflowStepCatalogEntry]:
        """Return a step catalog entry by type."""
        entry = self._entries.get(step_type)
        return entry.model_copy(deep=True) if entry else None

    def require(self, step_type: str) -> WorkflowStepCatalogEntry:
        """Return a step catalog entry or raise a helpful error."""
        entry = self.get(step_type)
        if not entry:
            raise KeyError(f"Unknown workflow step type: {step_type}")
        return entry

    def list(self) -> list[WorkflowStepCatalogEntry]:
        """Return all step catalog entries sorted by type."""
        return [
            entry.model_copy(deep=True)
            for _, entry in sorted(self._entries.items(), key=lambda item: item[0])
        ]

    def __contains__(self, step_type: object) -> bool:
        return isinstance(step_type, str) and step_type in self._entries


def create_default_step_registry() -> StepRegistry:
    """Create the default MVP workflow step catalog."""
    return StepRegistry(
        [
            WorkflowStepCatalogEntry(
                type="rag.query",
                display_name="RAG query",
                description="Retrieve documents from a RAG collection.",
                config_schema={
                    "type": "object",
                    "required": ["collection_id"],
                    "properties": {
                        "collection_id": {"type": "string"},
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1},
                        "since": {"type": "object"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "documents": {"type": "array"},
                        "count": {"type": "integer"},
                    },
                },
                required_permissions=["rag:read"],
                supports_retry=True,
                supports_test=True,
                estimated_cost_kind="retrieval",
            ),
            WorkflowStepCatalogEntry(
                type="agent.run",
                display_name="Run agent",
                description="Invoke a configured agent with workflow input.",
                config_schema={
                    "type": "object",
                    "required": ["agent_id", "prompt_template"],
                    "properties": {
                        "agent_id": {"type": "string"},
                        "prompt_template": {"type": "string"},
                        "input_mapping": {"type": "object"},
                        "max_tokens": {"type": "integer", "minimum": 1},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "usage": {"type": "object"},
                    },
                },
                required_permissions=["agent:execute"],
                supports_retry=True,
                supports_test=True,
                estimated_cost_kind="llm",
            ),
            WorkflowStepCatalogEntry(
                type="notify.in_app",
                display_name="In-app notification",
                description="Create an in-app notification for selected recipients.",
                config_schema={
                    "type": "object",
                    "required": ["recipients", "title_template"],
                    "properties": {
                        "recipients": {"type": "array", "items": {"type": "string"}},
                        "title_template": {"type": "string"},
                        "body_template": {"type": "string"},
                        "severity": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {"notification_ids": {"type": "array"}},
                },
                required_permissions=["notifications:create"],
                supports_retry=True,
                supports_test=False,
                estimated_cost_kind="none",
            ),
            WorkflowStepCatalogEntry(
                type="condition.no_results_skip",
                display_name="Skip when no results",
                description="Skip remaining steps when an input result set is empty.",
                config_schema={
                    "type": "object",
                    "required": ["input_step_key"],
                    "properties": {
                        "input_step_key": {"type": "string"},
                        "path": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "matched": {"type": "boolean"},
                        "action": {"type": "string"},
                    },
                },
                required_permissions=[],
                supports_retry=False,
                supports_test=True,
                estimated_cost_kind="none",
            ),
        ]
    )
