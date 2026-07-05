"""
Database models package
"""

from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.compiler import compiles

from app.db.database import Base


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PGUUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(32)"


@compiles(INET, "sqlite")
def _compile_inet_sqlite(type_, compiler, **kw):
    return "VARCHAR(45)"


from .agent_config import AgentConfig
from .api_key import APIKey
from .audit_log import AuditLog
from .billing_audit_log import ActionType as BillingActionType
from .billing_audit_log import ActorType as BillingActorType
from .billing_audit_log import (
    BillingAuditLog,
)
from .billing_audit_log import EntityType as BillingEntityType
from .budget import Budget
from .connector_source import (
    ConnectorSource,
    ConnectorStatus,
    ConnectorSyncJob,
    ConnectorSyncStatus,
    ConnectorType,
)
from .extract_job import ExtractJob
from .extract_result import ExtractResult
from .extract_template import ExtractTemplate
from .mcp_server import MCPServer
from .notification import (
    Notification,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    NotificationTemplate,
    NotificationType,
)
from .plugin import (
    Plugin,
    PluginAPIGateway,
    PluginAuditLog,
    PluginConfiguration,
    PluginCronJob,
    PluginInstance,
)
from .prompt_template import PromptTemplate
from .provider_pricing import PricingAuditLog, ProviderPricing
from .rag_collection import RagCollection
from .rag_document import RagDocument
from .role import Role, RoleLevel
from .security_event import SecurityEvent
from .tool import Tool, ToolCategory, ToolExecution, ToolStatus, ToolType
from .usage_record import UsageRecord
from .usage_tracking import UsageTracking
from .user import User
from .workflow import (
    LegacyWorkflowExecution,
    LegacyWorkflowStepLog,
    WorkflowArtifact,
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowRun,
    WorkflowStepRun,
    WorkflowTrigger,
    WorkflowVersion,
)

__all__ = [
    "Base",
    "User",
    "APIKey",
    "UsageTracking",
    "Budget",
    "AuditLog",
    "SecurityEvent",
    "RagCollection",
    "RagDocument",
    "PromptTemplate",
    "Plugin",
    "PluginConfiguration",
    "PluginInstance",
    "PluginAuditLog",
    "PluginCronJob",
    "PluginAPIGateway",
    "Role",
    "RoleLevel",
    "Tool",
    "ToolExecution",
    "ToolCategory",
    "ToolType",
    "ToolStatus",
    "Notification",
    "NotificationTemplate",
    "NotificationChannel",
    "NotificationType",
    "NotificationPriority",
    "NotificationStatus",
    "AgentConfig",
    "MCPServer",
    "UsageRecord",
    "ProviderPricing",
    "PricingAuditLog",
    "BillingAuditLog",
    "BillingEntityType",
    "BillingActionType",
    "BillingActorType",
    "ExtractTemplate",
    "ExtractJob",
    "ExtractResult",
    "ConnectorSource",
    "ConnectorSyncJob",
    "ConnectorType",
    "ConnectorStatus",
    "ConnectorSyncStatus",
    "LegacyWorkflowExecution",
    "LegacyWorkflowStepLog",
    "WorkflowDefinition",
    "WorkflowVersion",
    "WorkflowTrigger",
    "WorkflowRun",
    "WorkflowStepRun",
    "WorkflowArtifact",
    "WorkflowEvent",
]
