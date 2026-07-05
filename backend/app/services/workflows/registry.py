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
                category="RAG",
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
                category="Agent",
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
                category="Notification",
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
                category="Control",
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
            WorkflowStepCatalogEntry(
                type="condition.branch",
                display_name="Branch",
                description="Choose which later steps to skip based on a previous output.",
                category="Control",
                config_schema={
                    "type": "object",
                    "required": ["input_step_key", "operator"],
                    "properties": {
                        "input_step_key": {"type": "string"},
                        "path": {"type": "string"},
                        "operator": {
                            "type": "string",
                            "enum": [
                                "exists",
                                "empty",
                                "non_empty",
                                "equals",
                                "not_equals",
                                "contains",
                                "greater_than",
                                "greater_than_or_equal",
                                "less_than",
                                "less_than_or_equal",
                                "truthy",
                                "falsy",
                            ],
                        },
                        "value": {},
                        "matched_label": {"type": "string"},
                        "not_matched_label": {"type": "string"},
                        "matched_skip_step_keys": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "not_matched_skip_step_keys": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "matched": {"type": "boolean"},
                        "selected_label": {"type": "string"},
                        "skipped_step_keys": {"type": "array"},
                    },
                },
                required_permissions=[],
                supports_retry=False,
                supports_test=True,
                estimated_cost_kind="none",
                enabled=True,
            ),
            WorkflowStepCatalogEntry(
                type="connector.sync",
                display_name="Sync connector",
                description="Sync a connector and expose newly ingested records.",
                category="Connector",
                config_schema={
                    "type": "object",
                    "required": ["connector_id"],
                    "properties": {
                        "connector_id": {"type": "string"},
                        "since": {
                            "type": "string",
                            "enum": [
                                "connector_checkpoint",
                                "last_successful_run",
                                "full_sync",
                            ],
                        },
                        "max_records": {"type": "integer", "minimum": 1},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "items": {"type": "array"},
                        "count": {"type": "integer"},
                    },
                },
                required_permissions=["connectors:sync"],
                supports_retry=True,
                supports_test=False,
                estimated_cost_kind="connector",
                enabled=True,
            ),
            WorkflowStepCatalogEntry(
                type="extract.run_template",
                display_name="Run Extract template",
                description="Run an Extract template over selected documents.",
                category="Extract",
                config_schema={
                    "type": "object",
                    "required": ["template_id"],
                    "properties": {
                        "template_id": {"type": "string"},
                        "document_source": {
                            "type": "string",
                            "enum": ["previous_step", "rag_filter"],
                        },
                        "input_step_key": {"type": "string"},
                        "path": {"type": "string"},
                        "collection_id": {"type": "string"},
                        "connector_id": {"type": "string"},
                        "since": {
                            "type": "string",
                            "enum": ["last_successful_run", "all_matching"],
                        },
                        "max_documents": {"type": "integer", "minimum": 1},
                        "context": {"type": "object"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "results": {"type": "array"},
                    },
                },
                required_permissions=["extract:execute"],
                supports_retry=True,
                supports_test=False,
                estimated_cost_kind="extract",
                enabled=True,
            ),
        ]
    )
