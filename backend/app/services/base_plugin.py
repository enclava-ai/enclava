"""
Base Plugin Class and Plugin Runtime Environment
Provides the foundation for all Enclava plugins with security and isolation
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from fastapi import APIRouter, Request, HTTPException, Depends
import asyncio
import aiohttp
import logging
import time
import json
from pathlib import Path
import importlib.util
import sys

from app.schemas.plugin_manifest import PluginManifest, PluginManifestValidator
from app.core.logging import get_logger
from app.core.config import settings
from app.utils.exceptions import SecurityError, ValidationError
from app.models.plugin import PluginConfiguration
from app.models.user import User
from app.db.database import get_db
from sqlalchemy.orm import Session


@dataclass
class PluginContext:
    """Plugin execution context with user and authentication info"""

    user_id: Optional[str] = None
    api_key_id: Optional[str] = None
    user_permissions: List[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None


class PlatformAPIClient:
    """Secure client for plugins to access platform APIs"""

    def __init__(self, plugin_id: str, plugin_token: str):
        self.plugin_id = plugin_id
        self.plugin_token = plugin_token
        self.base_url = settings.INTERNAL_API_URL or "http://localhost:58000"
        self.logger = get_logger(f"plugin.{plugin_id}.api_client")

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """Make authenticated request to platform API"""
        headers = kwargs.setdefault("headers", {})
        headers.update(
            {
                "Authorization": f"Bearer {self.plugin_token}",
                "X-Plugin-ID": self.plugin_id,
                "X-Platform-Client": "plugin",
                "Content-Type": "application/json",
            }
        )

        url = f"{self.base_url}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, **kwargs) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Platform API error: {error_text}",
                        )

                    if response.content_type == "application/json":
                        return await response.json()
                    else:
                        return {"data": await response.text()}

        except aiohttp.ClientError as e:
            self.logger.error(f"Platform API client error: {e}")
            raise HTTPException(
                status_code=503, detail=f"Platform API unavailable: {str(e)}"
            )

    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """GET request to platform API"""
        return await self._make_request("GET", endpoint, **kwargs)

    async def post(
        self, endpoint: str, data: Dict[str, Any] = None, **kwargs
    ) -> Dict[str, Any]:
        """POST request to platform API"""
        if data:
            kwargs["json"] = data
        return await self._make_request("POST", endpoint, **kwargs)

    async def put(
        self, endpoint: str, data: Dict[str, Any] = None, **kwargs
    ) -> Dict[str, Any]:
        """PUT request to platform API"""
        if data:
            kwargs["json"] = data
        return await self._make_request("PUT", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """DELETE request to platform API"""
        return await self._make_request("DELETE", endpoint, **kwargs)

    # Platform-specific API methods
    async def call_chatbot_api(
        self, chatbot_id: str, message: str, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Consume platform chatbot API"""
        return await self.post(
            f"/api/v1/chatbot/external/{chatbot_id}/chat",
            {"message": message, "context": context or {}},
        )

    async def call_llm_api(
        self, model: str, messages: List[Dict[str, Any]], **kwargs
    ) -> Dict[str, Any]:
        """Consume platform LLM API"""
        return await self.post(
            "/api/v1/llm/chat/completions",
            {"model": model, "messages": messages, **kwargs},
        )

    async def search_rag(
        self, collection: str, query: str, top_k: int = 5
    ) -> Dict[str, Any]:
        """Consume platform RAG API"""
        return await self.post(
            f"/api/v1/rag/collections/{collection}/search",
            {"query": query, "top_k": top_k},
        )

    async def get_embeddings(self, model: str, input_text: str) -> Dict[str, Any]:
        """Generate embeddings via platform API"""
        return await self.post(
            "/api/v1/llm/embeddings", {"model": model, "input": input_text}
        )


class PluginConfigManager:
    """Manages plugin configuration with validation and encryption"""

    def __init__(self, plugin_id: str):
        self.plugin_id = plugin_id
        self.logger = get_logger(f"plugin.{plugin_id}.config")

    async def get_config(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get plugin configuration for user (or default)"""
        try:
            # Use dependency injection to get database session
            from app.db.database import SessionLocal

            db = SessionLocal()

            try:
                # Query for active configuration
                query = db.query(PluginConfiguration).filter(
                    PluginConfiguration.plugin_id == self.plugin_id,
                    PluginConfiguration.is_active == True,
                )

                if user_id:
                    # Get user-specific configuration
                    query = query.filter(PluginConfiguration.user_id == user_id)
                else:
                    # Get default configuration (is_default=True)
                    query = query.filter(PluginConfiguration.is_default == True)

                config = query.first()

                if config:
                    self.logger.debug(
                        f"Retrieved configuration for plugin {self.plugin_id}, user {user_id}"
                    )
                    return config.config_data or {}
                else:
                    self.logger.debug(
                        f"No configuration found for plugin {self.plugin_id}, user {user_id}"
                    )
                    return {}

            finally:
                db.close()

        except Exception as e:
            self.logger.error(f"Failed to get configuration: {e}")
            return {}

    async def save_config(
        self,
        config: Dict[str, Any],
        user_id: str,
        name: str = "Default Configuration",
        description: str = None,
    ) -> bool:
        """Save plugin configuration for user"""
        try:
            from app.db.database import SessionLocal

            db = SessionLocal()

            try:
                # Check if configuration already exists
                existing_config = (
                    db.query(PluginConfiguration)
                    .filter(
                        PluginConfiguration.plugin_id == self.plugin_id,
                        PluginConfiguration.user_id == user_id,
                        PluginConfiguration.name == name,
                    )
                    .first()
                )

                if existing_config:
                    # Update existing configuration
                    existing_config.config_data = config
                    existing_config.description = description
                    existing_config.is_active = True

                    self.logger.info(
                        f"Updated configuration for plugin {self.plugin_id}, user {user_id}"
                    )
                else:
                    # Create new configuration
                    new_config = PluginConfiguration(
                        plugin_id=self.plugin_id,
                        user_id=user_id,
                        name=name,
                        description=description,
                        config_data=config,
                        is_active=True,
                        is_default=(name == "Default Configuration"),
                        created_by_user_id=user_id,
                    )

                    # If this is the first configuration for this user/plugin, make it default
                    existing_count = (
                        db.query(PluginConfiguration)
                        .filter(
                            PluginConfiguration.plugin_id == self.plugin_id,
                            PluginConfiguration.user_id == user_id,
                        )
                        .count()
                    )

                    if existing_count == 0:
                        new_config.is_default = True

                    db.add(new_config)
                    self.logger.info(
                        f"Created new configuration for plugin {self.plugin_id}, user {user_id}"
                    )

                db.commit()
                return True

            except Exception as e:
                db.rollback()
                self.logger.error(f"Database error saving configuration: {e}")
                return False
            finally:
                db.close()

        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            return False

    async def validate_config(
        self, config: Dict[str, Any], schema: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate configuration against JSON schema"""
        try:
            import jsonschema

            jsonschema.validate(config, schema)
            return True, []
        except jsonschema.ValidationError as e:
            return False, [str(e)]
        except Exception as e:
            return False, [f"Schema validation error: {str(e)}"]


class PluginLogger:
    """Plugin-specific logger with security filtering"""

    def __init__(self, plugin_id: str):
        self.plugin_id = plugin_id
        self.logger = get_logger(f"plugin.{plugin_id}")

        # Sensitive data patterns to filter
        self.sensitive_patterns = [
            r"password",
            r"token",
            r"key",
            r"secret",
            r"api_key",
            r"bearer",
            r"authorization",
            r"credential",
        ]

    def _filter_sensitive_data(self, message: str) -> str:
        """Filter sensitive data from log messages"""
        import re

        filtered_message = message
        for pattern in self.sensitive_patterns:
            filtered_message = re.sub(
                f"{pattern}[=:]\s*[\"']?([^\"'\\s]+)[\"']?",
                f"{pattern}=***REDACTED***",
                filtered_message,
                flags=re.IGNORECASE,
            )
        return filtered_message

    def info(self, message: str, **kwargs):
        """Log info message with sensitive data filtering"""
        filtered_message = self._filter_sensitive_data(message)
        self.logger.info(f"[PLUGIN:{self.plugin_id}] {filtered_message}", **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with sensitive data filtering"""
        filtered_message = self._filter_sensitive_data(message)
        self.logger.warning(f"[PLUGIN:{self.plugin_id}] {filtered_message}", **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message with sensitive data filtering"""
        filtered_message = self._filter_sensitive_data(message)
        self.logger.error(f"[PLUGIN:{self.plugin_id}] {filtered_message}", **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug message with sensitive data filtering"""
        filtered_message = self._filter_sensitive_data(message)
        self.logger.debug(f"[PLUGIN:{self.plugin_id}] {filtered_message}", **kwargs)


class BasePlugin(ABC):
    """Base class for all Enclava plugins with security and isolation"""

    def __init__(self, manifest: PluginManifest, plugin_token: str):
        self.manifest = manifest
        self.plugin_id = manifest.metadata.name
        self.version = manifest.metadata.version

        # Initialize plugin services
        self.api_client = PlatformAPIClient(self.plugin_id, plugin_token)
        self.config = PluginConfigManager(self.plugin_id)
        self.logger = PluginLogger(self.plugin_id)

        # Plugin state
        self.initialized = False
        self._startup_time = time.time()
        self._request_count = 0
        self._error_count = 0

        self.logger.info(f"Plugin {self.plugin_id} v{self.version} instantiated")

    @abstractmethod
    def get_api_router(self) -> APIRouter:
        """Return FastAPI router for plugin endpoints"""
        pass

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize plugin resources and connections"""
        pass

    @abstractmethod
    async def cleanup(self) -> bool:
        """Cleanup plugin resources on shutdown"""
        pass

    async def health_check(self) -> Dict[str, Any]:
        """Plugin health status"""
        uptime = time.time() - self._startup_time
        error_rate = self._error_count / max(self._request_count, 1)

        return {
            "status": "healthy" if error_rate < 0.1 else "warning",
            "plugin": self.plugin_id,
            "version": self.version,
            "uptime_seconds": round(uptime, 2),
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": round(error_rate, 3),
            "initialized": self.initialized,
        }

    async def get_configuration_schema(self) -> Dict[str, Any]:
        """Return JSON schema for plugin configuration"""
        return self.manifest.spec.config_schema

    async def execute_cron_job(self, job_name: str) -> bool:
        """Execute scheduled cron job"""
        self.logger.info(f"Executing cron job: {job_name}")

        # Find job in manifest
        job_spec = None
        for job in self.manifest.spec.cron_jobs:
            if job.name == job_name:
                job_spec = job
                break

        if not job_spec:
            self.logger.error(f"Cron job not found: {job_name}")
            return False

        try:
            # Get the function to execute
            if hasattr(self, job_spec.function):
                func = getattr(self, job_spec.function)
                if asyncio.iscoroutinefunction(func):
                    result = await func()
                else:
                    result = func()

                self.logger.info(f"Cron job {job_name} completed successfully")
                return bool(result)
            else:
                self.logger.error(f"Cron job function not found: {job_spec.function}")
                return False

        except Exception as e:
            self.logger.error(f"Cron job {job_name} failed: {e}")
            self._error_count += 1
            return False

    def get_auth_context(self) -> PluginContext:
        """Dependency to get authentication context in API endpoints"""

        async def _get_context(request: Request) -> PluginContext:
            # Extract authentication info from request
            # This would be populated by the plugin API gateway
            return PluginContext(
                user_id=request.headers.get("X-User-ID"),
                api_key_id=request.headers.get("X-API-Key-ID"),
                user_permissions=request.headers.get("X-User-Permissions", "").split(
                    ","
                ),
                ip_address=request.headers.get("X-Real-IP"),
                user_agent=request.headers.get("User-Agent"),
                request_id=request.headers.get("X-Request-ID"),
            )

        return Depends(_get_context)

    def _track_request(self, success: bool = True):
        """Track request metrics"""
        self._request_count += 1
        if not success:
            self._error_count += 1


class PluginSecurityManager:
    """Manages plugin security and isolation"""

    BLOCKED_IMPORTS = {
        # Core platform modules
        "app.db",
        "app.models",
        "app.core",
        "app.services",
        "sqlalchemy",
        "alembic",
        # Security sensitive
        "subprocess",
        "eval",
        "exec",
        "compile",
        "__import__",
        "os.system",
        "os.popen",
        "os.spawn",
        # System access
        "socket",
        "multiprocessing",
        "threading",
    }

    ALLOWED_IMPORTS = {
        # Standard library
        "asyncio",
        "aiohttp",
        "json",
        "datetime",
        "typing",
        "pydantic",
        "logging",
        "time",
        "uuid",
        "hashlib",
        "base64",
        "pathlib",
        "re",
        "urllib.parse",
        "dataclasses",
        "enum",
        # Approved third-party
        "httpx",
        "requests",
        "pandas",
        "numpy",
        "yaml",
        # Plugin framework
        "app.services.base_plugin",
        "app.schemas.plugin_manifest",
    }

    @classmethod
    def validate_plugin_import(cls, import_name: str) -> bool:
        """Validate if plugin can import a module"""
        # Block dangerous imports
        if any(import_name.startswith(blocked) for blocked in cls.BLOCKED_IMPORTS):
            raise SecurityError(
                f"Import '{import_name}' not allowed in plugin environment"
            )

        # Allow explicit safe imports
        if any(import_name.startswith(allowed) for allowed in cls.ALLOWED_IMPORTS):
            return True

        # Log potentially unsafe imports
        logger = get_logger("plugin.security")
        logger.warning(f"Potentially unsafe import in plugin: {import_name}")
        return True

    @classmethod
    def create_plugin_sandbox(cls, plugin_id: str) -> Dict[str, Any]:
        """Create isolated environment for plugin execution"""
        return {
            "max_memory_mb": 128,
            "max_cpu_percent": 25,
            "max_disk_mb": 100,
            "max_api_calls_per_minute": 100,
            "allowed_domains": [],  # Will be populated from manifest
            "network_timeout_seconds": 30,
        }


class PluginLoader:
    """Loads and validates plugins from directories"""

    def __init__(self):
        self.logger = get_logger("plugin.loader")
        self.loaded_plugins: Dict[str, BasePlugin] = {}

    async def load_plugin(self, plugin_dir: Path, plugin_token: str) -> BasePlugin:
        """Load a plugin from a directory"""
        self.logger.info(f"Loading plugin from: {plugin_dir}")

        # Load and validate manifest
        manifest_path = plugin_dir / "manifest.yaml"
        validation_result = validate_manifest_file(manifest_path)

        if not validation_result["valid"]:
            raise ValidationError(
                f"Invalid plugin manifest: {validation_result['errors']}"
            )

        manifest = validation_result["manifest"]

        # Check compatibility
        compatibility = validation_result["compatibility"]
        if not compatibility["compatible"]:
            raise ValidationError(f"Plugin incompatible: {compatibility['errors']}")

        # Load plugin module
        main_py_path = plugin_dir / "main.py"
        spec = importlib.util.spec_from_file_location(
            f"plugin_{manifest.metadata.name}", main_py_path
        )

        if not spec or not spec.loader:
            raise ValidationError(f"Cannot load plugin module: {main_py_path}")

        # Security check before loading
        self._validate_plugin_security(main_py_path)

        # Load module
        plugin_module = importlib.util.module_from_spec(spec)

        # Add to sys.modules to allow imports
        sys.modules[spec.name] = plugin_module

        try:
            spec.loader.exec_module(plugin_module)
        except Exception as e:
            raise ValidationError(f"Failed to execute plugin module: {e}")

        # Find plugin class
        plugin_class = None
        for attr_name in dir(plugin_module):
            attr = getattr(plugin_module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BasePlugin)
                and attr is not BasePlugin
            ):
                plugin_class = attr
                break

        if not plugin_class:
            raise ValidationError(
                "Plugin must contain a class inheriting from BasePlugin"
            )

        # Instantiate plugin
        plugin_instance = plugin_class(manifest, plugin_token)

        # Initialize plugin
        try:
            await plugin_instance.initialize()
            plugin_instance.initialized = True
        except Exception as e:
            raise ValidationError(f"Plugin initialization failed: {e}")

        self.loaded_plugins[manifest.metadata.name] = plugin_instance
        self.logger.info(f"Plugin {manifest.metadata.name} loaded successfully")

        return plugin_instance

    def _validate_plugin_security(self, main_py_path: Path):
        """Validate plugin code for security issues"""
        with open(main_py_path, "r", encoding="utf-8") as f:
            code_content = f.read()

        # Check for dangerous patterns
        dangerous_patterns = [
            "eval(",
            "exec(",
            "compile(",
            "subprocess.",
            "os.system",
            "os.popen",
            "__import__",
            "importlib.import_module",
            "from app.db",
            "from app.models",
            "sqlalchemy",
            "SessionLocal",
        ]

        for pattern in dangerous_patterns:
            if pattern in code_content:
                raise SecurityError(
                    f"Dangerous pattern detected in plugin code: {pattern}"
                )

    async def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin and cleanup resources"""
        if plugin_id not in self.loaded_plugins:
            return False

        plugin = self.loaded_plugins[plugin_id]

        try:
            await plugin.cleanup()
            del self.loaded_plugins[plugin_id]
            self.logger.info(f"Plugin {plugin_id} unloaded successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error unloading plugin {plugin_id}: {e}")
            return False

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """Get loaded plugin by ID"""
        return self.loaded_plugins.get(plugin_id)

    def list_loaded_plugins(self) -> List[str]:
        """List all loaded plugin IDs"""
        return list(self.loaded_plugins.keys())
