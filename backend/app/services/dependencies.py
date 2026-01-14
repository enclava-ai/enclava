"""
Service Dependencies for FastAPI Dependency Injection

This module provides FastAPI-compatible dependency functions for core services.
Using these dependencies instead of direct imports enables:
- Easy mocking in tests via app.dependency_overrides
- Explicit dependency declaration in route signatures
- Consistent service access patterns

Usage in routes:
    from app.services.dependencies import ModuleManagerDep, LLMServiceDep

    @router.get("/modules")
    async def list_modules(module_manager: ModuleManagerDep):
        return module_manager.list_modules()

Usage in tests:
    from app.services.dependencies import get_llm_service

    app.dependency_overrides[get_llm_service] = lambda: mock_llm_service
"""

from typing import Annotated, TYPE_CHECKING
from fastapi import Depends, Request

if TYPE_CHECKING:
    from app.services.module_manager import ModuleManager
    from app.services.llm.service import LLMService
    from app.services.plugin_registry import PluginInstaller, PluginDiscoveryService


def get_module_manager(request: Request) -> "ModuleManager":
    """
    Get the module manager instance from app state.

    The module manager is initialized during app startup and stored in app.state.
    This dependency provides access to it with proper typing.
    """
    return request.app.state.module_manager


def get_llm_service() -> "LLMService":
    """
    Get the LLM service singleton.

    Returns the global LLM service instance. The service is initialized
    during app startup via the lifespan handler.
    """
    from app.services.llm.service import llm_service

    return llm_service


def get_plugin_installer() -> "PluginInstaller":
    """
    Get the plugin installer singleton.

    Returns the global plugin installer instance for managing
    plugin installation, updates, and removal.
    """
    from app.services.plugin_registry import plugin_installer

    return plugin_installer


def get_plugin_discovery() -> "PluginDiscoveryService":
    """
    Get the plugin discovery service singleton.

    Returns the global plugin discovery service for searching
    and listing available plugins.
    """
    from app.services.plugin_registry import plugin_discovery

    return plugin_discovery


# Type aliases for cleaner dependency injection in route signatures
ModuleManagerDep = Annotated["ModuleManager", Depends(get_module_manager)]
LLMServiceDep = Annotated["LLMService", Depends(get_llm_service)]
PluginInstallerDep = Annotated["PluginInstaller", Depends(get_plugin_installer)]
PluginDiscoveryDep = Annotated["PluginDiscoveryService", Depends(get_plugin_discovery)]
