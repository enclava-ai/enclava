"""
Connector registry.

Maps ConnectorType enum values to their implementation classes.
New connectors are registered with the @register decorator, which keeps
imports lazy — a connector's dependencies (e.g. slack-sdk) are only imported
when that connector type is actually instantiated.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from app.models.connector_source import ConnectorType

if TYPE_CHECKING:
    from app.connectors.base import BaseConnector

# Registry: ConnectorType -> (module_path, class_name)
# We store strings rather than class objects so that connector-specific
# third-party dependencies are only imported on demand.
_REGISTRY: dict[ConnectorType, tuple[str, str]] = {
    ConnectorType.NOTION: (
        "app.connectors.notion",
        "NotionConnector",
    ),
    ConnectorType.SLACK: (
        "app.connectors.slack",
        "SlackConnector",
    ),
    ConnectorType.GITHUB: (
        "app.connectors.github",
        "GitHubConnector",
    ),
    ConnectorType.LINEAR: (
        "app.connectors.linear",
        "LinearConnector",
    ),
    ConnectorType.GOOGLE_DRIVE: (
        "app.connectors.google_drive",
        "GoogleDriveConnector",
    ),
    ConnectorType.GOOGLE_DOCS: (
        "app.connectors.google_drive",
        "GoogleDriveConnector",
    ),
    ConnectorType.CONFLUENCE: (
        "app.connectors.confluence",
        "ConfluenceConnector",
    ),
    ConnectorType.JIRA: (
        "app.connectors.jira",
        "JiraConnector",
    ),
}

# Module-level cache so each class is imported at most once per process
_cache: dict[ConnectorType, type[BaseConnector]] = {}


class ConnectorNotFoundError(Exception):
    pass


def get_connector_class(connector_type: ConnectorType) -> type[BaseConnector]:
    """
    Return the connector class for *connector_type*.

    Raises ConnectorNotFoundError if no connector is registered for that type.
    """
    if connector_type in _cache:
        return _cache[connector_type]

    entry = _REGISTRY.get(connector_type)
    if entry is None:
        raise ConnectorNotFoundError(
            f"No connector registered for type '{connector_type}'. "
            f"Available types: {list(_REGISTRY.keys())}"
        )

    module_path, class_name = entry
    try:
        module = importlib.import_module(module_path)
        cls: type[BaseConnector] = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        raise ConnectorNotFoundError(
            f"Failed to load connector '{connector_type}' "
            f"from {module_path}.{class_name}: {exc}"
        ) from exc

    _cache[connector_type] = cls
    return cls


def build_connector(
    connector_type: ConnectorType,
    config: dict,
    credentials: dict,
) -> BaseConnector:
    """
    Convenience factory: load the class, instantiate with config, and inject
    decrypted credentials — ready to call validate() or fetch_*().
    """
    cls = get_connector_class(connector_type)
    connector = cls(config=config)
    connector.load_credentials(credentials)
    return connector


def available_connector_types() -> list[ConnectorType]:
    """Return all registered connector types."""
    return list(_REGISTRY.keys())
