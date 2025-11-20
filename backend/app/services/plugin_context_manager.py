"""
Plugin Context Manager
Standardized plugin context management for single-tenant deployments
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import time
import uuid
import logging

logger = logging.getLogger(__name__)


class PluginContextManager:
    """Standardized plugin context management for single-tenant deployments"""

    def __init__(self):
        self.active_contexts: Dict[str, Dict[str, Any]] = {}

    def create_plugin_context(
        self, plugin_id: str, user_id: str, session_type: str = "interactive"
    ) -> Dict[str, Any]:
        """Generate standardized plugin execution context"""
        context_id = f"{plugin_id}_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        context = {
            "context_id": context_id,
            "plugin_id": plugin_id,
            "user_id": user_id,
            "session_type": session_type,  # interactive, api, scheduled
            "created_at": datetime.utcnow().isoformat(),
            "capabilities": self._get_plugin_capabilities(plugin_id),
            "resource_limits": self._get_resource_limits(plugin_id),
            "audit_trail": [],
            "metadata": {},
        }

        # Cache active context for tracking
        self.active_contexts[context_id] = context
        logger.info(f"Created plugin context {context_id} for {plugin_id}")

        return context

    def get_context(self, context_id: str) -> Optional[Dict[str, Any]]:
        """Get existing plugin context by ID"""
        return self.active_contexts.get(context_id)

    def update_context_metadata(
        self, context_id: str, metadata: Dict[str, Any]
    ) -> bool:
        """Update metadata for an existing context"""
        if context_id in self.active_contexts:
            self.active_contexts[context_id]["metadata"].update(metadata)
            return True
        return False

    def add_audit_trail_entry(
        self, context_id: str, action: str, details: Dict[str, Any]
    ) -> bool:
        """Add entry to context audit trail"""
        if context_id in self.active_contexts:
            audit_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "action": action,
                "details": details,
            }
            self.active_contexts[context_id]["audit_trail"].append(audit_entry)
            return True
        return False

    def destroy_context(self, context_id: str) -> bool:
        """Remove context from active tracking"""
        if context_id in self.active_contexts:
            plugin_id = self.active_contexts[context_id]["plugin_id"]
            del self.active_contexts[context_id]
            logger.info(f"Destroyed plugin context {context_id} for {plugin_id}")
            return True
        return False

    def cleanup_old_contexts(self, max_age_hours: int = 24) -> int:
        """Remove contexts older than specified hours"""
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)

        contexts_to_remove = []
        for context_id, context in self.active_contexts.items():
            try:
                created_timestamp = datetime.fromisoformat(
                    context["created_at"]
                ).timestamp()
                if created_timestamp < cutoff_time:
                    contexts_to_remove.append(context_id)
            except Exception as e:
                logger.warning(
                    f"Could not parse creation time for context {context_id}: {e}"
                )
                contexts_to_remove.append(context_id)  # Remove invalid contexts

        removed_count = 0
        for context_id in contexts_to_remove:
            if self.destroy_context(context_id):
                removed_count += 1

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old plugin contexts")

        return removed_count

    def get_user_contexts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active contexts for a user"""
        user_contexts = []
        for context in self.active_contexts.values():
            if context["user_id"] == user_id:
                user_contexts.append(context)
        return user_contexts

    def get_plugin_contexts(self, plugin_id: str) -> List[Dict[str, Any]]:
        """Get all active contexts for a plugin"""
        plugin_contexts = []
        for context in self.active_contexts.values():
            if context["plugin_id"] == plugin_id:
                plugin_contexts.append(context)
        return plugin_contexts

    def validate_context(self, context_id: str, plugin_id: str, user_id: str) -> bool:
        """Validate that context belongs to the specified plugin and user"""
        context = self.get_context(context_id)
        if not context:
            return False

        return context["plugin_id"] == plugin_id and context["user_id"] == user_id

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about active contexts"""
        total_contexts = len(self.active_contexts)

        # Count by session type
        session_types = {}
        plugins = set()
        users = set()

        for context in self.active_contexts.values():
            session_type = context.get("session_type", "unknown")
            session_types[session_type] = session_types.get(session_type, 0) + 1
            plugins.add(context["plugin_id"])
            users.add(context["user_id"])

        return {
            "total_contexts": total_contexts,
            "unique_plugins": len(plugins),
            "unique_users": len(users),
            "session_types": session_types,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _get_plugin_capabilities(self, plugin_id: str) -> List[str]:
        """Get plugin capabilities from manifest"""
        # In a real implementation, this would read from the plugin manifest
        # For now, return basic capabilities for single-tenant deployment
        return ["core_api", "user_data", "filesystem_read"]

    def _get_resource_limits(self, plugin_id: str) -> Dict[str, Any]:
        """Get resource limits for plugin"""
        # Default resource limits for single-tenant deployment
        # These are more relaxed than multi-tenant limits
        return {
            "max_memory_mb": 256,  # Increased from 128 for single-tenant
            "max_cpu_percent": 50,  # Increased from 25 for single-tenant
            "max_execution_time_seconds": 600,  # Increased from 300
            "max_api_calls_per_minute": 200,  # Reasonable limit
            "max_file_size_mb": 50,  # File handling limit
        }

    def generate_plugin_token(self, context_id: str) -> str:
        """Generate a simple token based on context ID"""
        # For single-tenant deployment, we can use a simpler token approach
        # This is not for security isolation, just for tracking and logging
        context = self.get_context(context_id)
        if not context:
            return f"invalid_context_{int(time.time())}"

        # Create a simple token that includes context information
        token_data = f"{context['plugin_id']}:{context['user_id']}:{context_id}"
        # In a real implementation, you might want to encode/encrypt this
        return f"plg_{token_data.replace(':', '_')}"


# Global instance for single-tenant deployment
plugin_context_manager = PluginContextManager()
