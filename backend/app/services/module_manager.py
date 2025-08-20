"""
Module management service with dynamic discovery
"""
import asyncio
import importlib
import os
import sys
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.core.config import settings
from app.core.logging import log_module_event, get_logger
from app.utils.exceptions import ModuleLoadError, ModuleNotFoundError
from app.services.permission_manager import permission_registry
from app.services.module_config_manager import module_config_manager, ModuleManifest

logger = get_logger(__name__)


@dataclass
class ModuleConfig:
    """Configuration for a module"""
    name: str
    enabled: bool = True
    config: Dict[str, Any] = None
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}
        if self.dependencies is None:
            self.dependencies = []


class ModuleFileWatcher(FileSystemEventHandler):
    """Watch for changes in module files"""
    
    def __init__(self, module_manager):
        self.module_manager = module_manager
        
    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.py'):
            return
            
        # Extract module name from path
        path_parts = Path(event.src_path).parts
        if 'modules' in path_parts:
            modules_index = path_parts.index('modules')
            if modules_index + 1 < len(path_parts):
                module_name = path_parts[modules_index + 1]
                if module_name in self.module_manager.modules:
                    log_module_event("hot_reload", "file_changed", {
                        "module": module_name,
                        "file": event.src_path
                    })
                    # Schedule reload
                    asyncio.create_task(self.module_manager.reload_module(module_name))


class ModuleManager:
    """Manages loading, unloading, and execution of modules"""
    
    def __init__(self):
        self.modules: Dict[str, Any] = {}
        self.module_configs: Dict[str, ModuleConfig] = {}
        self.module_order: List[str] = []
        self.initialized = False
        self.hot_reload_enabled = True
        self.file_observer = None
        self.fastapi_app = None
    
    async def initialize(self, fastapi_app=None):
        """Initialize the module manager and load all modules"""
        if self.initialized:
            return
        
        # Store FastAPI app reference for router registration
        self.fastapi_app = fastapi_app
        
        log_module_event("module_manager", "initializing", {"action": "start"})
        
        try:
            # Load module configurations
            await self._load_module_configs()
            
            # Load and initialize modules
            await self._load_modules()
            
            self.initialized = True
            log_module_event("module_manager", "initialized", {
                "modules_count": len(self.modules),
                "enabled_modules": [name for name, config in self.module_configs.items() if config.enabled]
            })
            
        except Exception as e:
            log_module_event("module_manager", "initialization_failed", {"error": str(e)})
            raise ModuleLoadError(f"Failed to initialize module manager: {str(e)}")
    
    async def _load_module_configs(self):
        """Load module configurations from dynamic discovery"""
        # Initialize permission system
        permission_registry.register_platform_permissions()
        
        # Discover modules dynamically from filesystem
        try:
            discovered_manifests = await module_config_manager.discover_modules("modules")
            
            # Load saved configurations
            await module_config_manager.load_saved_configs()
            
            # Filter out core infrastructure that shouldn't be pluggable modules
            EXCLUDED_MODULES = ["cache"]  # Cache is now core infrastructure
            
            # Convert manifests to ModuleConfig objects
            for name, manifest in discovered_manifests.items():
                # Skip modules that are now core infrastructure
                if name in EXCLUDED_MODULES:
                    logger.info(f"Skipping module '{name}' - now integrated as core infrastructure")
                    continue
                    
                saved_config = module_config_manager.get_module_config(name)
                
                module_config = ModuleConfig(
                    name=manifest.name,
                    enabled=manifest.enabled,
                    config=saved_config,
                    dependencies=manifest.dependencies
                )
                
                self.module_configs[name] = module_config
                
                log_module_event(name, "discovered", {
                    "version": manifest.version,
                    "description": manifest.description,
                    "enabled": manifest.enabled,
                    "dependencies": manifest.dependencies
                })
            
            logger.info(f"Discovered {len(discovered_manifests)} modules: {list(discovered_manifests.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to discover modules: {e}")
            # Fallback to legacy hard-coded modules
            await self._load_legacy_modules()
        
        # Start file watcher for hot-reload
        if self.hot_reload_enabled:
            await self._start_file_watcher()
    
    async def _load_legacy_modules(self):
        """Fallback to legacy hard-coded module loading"""
        logger.warning("Falling back to legacy module configuration")
        
        default_modules = [
            ModuleConfig(name="rag", enabled=True, config={}),
            ModuleConfig(name="workflow", enabled=True, config={})
        ]
        
        for config in default_modules:
            self.module_configs[config.name] = config
    
    async def _load_modules(self):
        """Load all enabled modules"""
        # Sort modules by dependencies
        self._sort_modules_by_dependencies()
        
        for module_name in self.module_order:
            config = self.module_configs[module_name]
            if config.enabled:
                await self._load_module(module_name, config)
    
    def _sort_modules_by_dependencies(self):
        """Sort modules by their dependencies using topological sort"""
        # Simple topological sort
        visited = set()
        temp_visited = set()
        self.module_order = []
        
        def visit(module_name: str):
            if module_name in temp_visited:
                raise ModuleLoadError(f"Circular dependency detected involving module: {module_name}")
            if module_name in visited:
                return
            
            temp_visited.add(module_name)
            
            # Visit dependencies first
            config = self.module_configs.get(module_name)
            if config and config.dependencies:
                for dep in config.dependencies:
                    if dep in self.module_configs:
                        visit(dep)
            
            temp_visited.remove(module_name)
            visited.add(module_name)
            self.module_order.append(module_name)
        
        for module_name in self.module_configs:
            if module_name not in visited:
                visit(module_name)
    
    async def _load_module(self, module_name: str, config: ModuleConfig):
        """Load a single module"""
        try:
            log_module_event(module_name, "loading", {"config": config.config})
            
            # Check if module exists in the modules directory
            # Try multiple possible locations in order of preference
            possible_paths = [
                Path(f"modules/{module_name}"),  # Docker container path
                Path(f"modules/{module_name}"),  # Container path
                Path(f"app/modules/{module_name}")  # Legacy path
            ]
            
            module_dir = None
            modules_base_path = None
            
            for path in possible_paths:
                if path.exists():
                    module_dir = path
                    modules_base_path = path.parent
                    break
            
            if module_dir and module_dir.exists():
                # Use direct import from modules directory
                module_path = f"modules.{module_name}.main"
                
                # Add modules directory to Python path if not already there
                modules_path_str = str(modules_base_path.absolute())
                if modules_path_str not in sys.path:
                    sys.path.insert(0, modules_path_str)
                
                # Force reload if already imported
                if module_path in sys.modules:
                    importlib.reload(sys.modules[module_path])
                    module = sys.modules[module_path]
                else:
                    module = importlib.import_module(module_path)
            else:
                # Final fallback - try app.modules path (legacy)
                try:
                    module_path = f"app.modules.{module_name}.main"
                    module = importlib.import_module(module_path)
                except ImportError:
                    raise ModuleLoadError(f"Module {module_name} not found in any expected location: {[str(p) for p in possible_paths]}")
            
            # Get the module instance - try multiple patterns
            module_instance = None
            
            # Pattern 1: {module_name}_module (e.g., cache_module)
            if hasattr(module, f'{module_name}_module'):
                module_instance = getattr(module, f'{module_name}_module')
            # Pattern 2: Just 'module' attribute
            elif hasattr(module, 'module'):
                module_instance = getattr(module, 'module')
            # Pattern 3: Module class with same name as module (e.g., CacheModule)
            elif hasattr(module, f'{module_name.title()}Module'):
                module_class = getattr(module, f'{module_name.title()}Module')
                if callable(module_class):
                    module_instance = module_class()
                else:
                    module_instance = module_class
            # Pattern 4: Use the module itself as fallback
            else:
                module_instance = module
            
            self.modules[module_name] = module_instance
            
            # Initialize the module if it has an init function
            module_initialized = False
            if hasattr(self.modules[module_name], 'initialize'):
                try:
                    import inspect
                    init_method = self.modules[module_name].initialize
                    sig = inspect.signature(init_method)
                    param_count = len([p for p in sig.parameters.values() if p.name != 'self'])
                    
                    if hasattr(self.modules[module_name], 'config'):
                        # Pass config if it's a BaseModule
                        self.modules[module_name].config.update(config.config)
                        await self.modules[module_name].initialize()
                    elif param_count > 0:
                        # Legacy module - pass config as parameter
                        await self.modules[module_name].initialize(config.config)
                    else:
                        # Module initialize method takes no parameters
                        await self.modules[module_name].initialize()
                    module_initialized = True
                    log_module_event(module_name, "initialized", {"success": True})
                except Exception as e:
                    log_module_event(module_name, "initialization_failed", {"error": str(e)})
                    module_initialized = False
            else:
                # Module doesn't have initialize method, mark as initialized anyway
                module_initialized = True
            
            # Mark module initialization status (safely)
            try:
                self.modules[module_name].initialized = module_initialized
            except AttributeError:
                # Module doesn't support the initialized attribute, that's okay
                pass
            
            # Register module permissions - check both new and legacy methods
            permissions = []
            
            # New BaseModule method
            if hasattr(self.modules[module_name], 'get_required_permissions'):
                try:
                    permissions = self.modules[module_name].get_required_permissions()
                    log_module_event(module_name, "permissions_registered", {
                        "permissions_count": len(permissions),
                        "type": "BaseModule"
                    })
                except Exception as e:
                    log_module_event(module_name, "permissions_failed", {"error": str(e)})
            
            # Legacy method
            elif hasattr(self.modules[module_name], 'get_permissions'):
                try:
                    permissions = self.modules[module_name].get_permissions()
                    log_module_event(module_name, "permissions_registered", {
                        "permissions_count": len(permissions),
                        "type": "legacy"
                    })
                except Exception as e:
                    log_module_event(module_name, "permissions_failed", {"error": str(e)})
            
            # Register permissions with the permission system
            if permissions:
                permission_registry.register_module(module_name, permissions)
            
            # Register module router with FastAPI app if available
            await self._register_module_router(module_name, self.modules[module_name])
            
            log_module_event(module_name, "loaded", {"success": True})
            
        except ImportError as e:
            error_msg = f"Module {module_name} import failed: {str(e)}"
            log_module_event(module_name, "load_failed", {"error": error_msg, "type": "ImportError"})
            # For critical modules, we might want to fail completely
            if module_name in ['security', 'cache']:
                raise ModuleLoadError(error_msg)
            # For optional modules, log warning but continue
            import warnings
            warnings.warn(f"Optional module {module_name} failed to load: {str(e)}")
        except Exception as e:
            error_msg = f"Module {module_name} loading failed: {str(e)}"
            log_module_event(module_name, "load_failed", {"error": error_msg, "type": type(e).__name__})
            # For critical modules, we might want to fail completely  
            if module_name in ['security', 'cache']:
                raise ModuleLoadError(error_msg)
            # For optional modules, log warning but continue
            import warnings
            warnings.warn(f"Optional module {module_name} failed to load: {str(e)}")
    
    async def _register_module_router(self, module_name: str, module_instance):
        """Register a module's router with the FastAPI app if it has one"""
        if not self.fastapi_app or not module_instance:
            return
        
        try:
            # Check if module has a router attribute
            if hasattr(module_instance, 'router'):
                router = getattr(module_instance, 'router')
                
                # Verify it's actually a FastAPI router
                from fastapi import APIRouter
                if isinstance(router, APIRouter):
                    # Register the router with the app
                    self.fastapi_app.include_router(router)
                    
                    log_module_event(module_name, "router_registered", {
                        "router_prefix": getattr(router, 'prefix', 'unknown'),
                        "router_tags": getattr(router, 'tags', [])
                    })
                    
                    logger.info(f"Registered router for module {module_name}")
                else:
                    logger.debug(f"Module {module_name} has 'router' attribute but it's not a FastAPI router")
            else:
                logger.debug(f"Module {module_name} does not have a router")
                
        except Exception as e:
            log_module_event(module_name, "router_registration_failed", {
                "error": str(e)
            })
            logger.warning(f"Failed to register router for module {module_name}: {e}")
    
    async def unload_module(self, module_name: str):
        """Unload a module"""
        if module_name not in self.modules:
            raise ModuleNotFoundError(f"Module {module_name} not loaded")
        
        try:
            module = self.modules[module_name]
            
            # Call cleanup if available
            if hasattr(module, 'cleanup'):
                await module.cleanup()
            
            del self.modules[module_name]
            log_module_event(module_name, "unloaded", {"success": True})
            
        except Exception as e:
            log_module_event(module_name, "unload_failed", {"error": str(e)})
            raise ModuleLoadError(f"Failed to unload module {module_name}: {str(e)}")
    
    async def reload_module(self, module_name: str) -> bool:
        """Reload a module"""
        log_module_event(module_name, "reloading", {})
        
        try:
            if module_name in self.modules:
                await self.unload_module(module_name)
            
            config = self.module_configs.get(module_name)
            if config and config.enabled:
                await self._load_module(module_name, config)
                log_module_event(module_name, "reloaded", {"success": True})
                return True
            else:
                log_module_event(module_name, "reload_skipped", {"reason": "Module disabled or no config"})
                return False
        except Exception as e:
            log_module_event(module_name, "reload_failed", {"error": str(e)})
            return False
    
    def get_module(self, module_name: str) -> Optional[Any]:
        """Get a loaded module"""
        return self.modules.get(module_name)
    
    def list_modules(self) -> List[str]:
        """List all loaded modules"""
        return list(self.modules.keys())
    
    def is_module_loaded(self, module_name: str) -> bool:
        """Check if a module is loaded"""
        return module_name in self.modules
    
    async def execute_interceptor_chain(self, chain_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute interceptor chain for all loaded modules"""
        result_context = context.copy()
        
        for module_name in self.module_order:
            if module_name in self.modules:
                module = self.modules[module_name]
                
                # Check if module has the interceptor
                interceptor_method = f"{chain_type}_interceptor"
                if hasattr(module, interceptor_method):
                    try:
                        interceptor = getattr(module, interceptor_method)
                        result_context = await interceptor(result_context)
                        
                        log_module_event(module_name, "interceptor_executed", {
                            "chain_type": chain_type,
                            "success": True
                        })
                    except Exception as e:
                        log_module_event(module_name, "interceptor_failed", {
                            "chain_type": chain_type,
                            "error": str(e)
                        })
                        # Continue with other modules even if one fails
                        continue
        
        return result_context
    
    async def shutdown(self):
        """Shutdown all modules"""
        if not self.initialized:
            return
        
        log_module_event("module_manager", "shutting_down", {"modules_count": len(self.modules)})
        
        # Unload modules in reverse order
        for module_name in reversed(self.module_order):
            if module_name in self.modules:
                try:
                    await self.unload_module(module_name)
                except Exception as e:
                    log_module_event(module_name, "shutdown_error", {"error": str(e)})
        
        self.initialized = False
        log_module_event("module_manager", "shutdown_complete", {"success": True})
    
    async def cleanup(self):
        """Cleanup method - alias for shutdown"""
        await self.shutdown()
    
    async def _start_file_watcher(self):
        """Start watching module files for changes"""
        try:
            # Try multiple possible locations for modules directory
            possible_modules_paths = [
                Path("modules"),  # Docker container path
                Path("modules"),  # Container path
                Path("app/modules")  # Legacy path
            ]
            
            modules_path = None
            for path in possible_modules_paths:
                if path.exists():
                    modules_path = path
                    break
            
            if modules_path and modules_path.exists():
                self.file_observer = Observer()
                event_handler = ModuleFileWatcher(self)
                self.file_observer.schedule(event_handler, str(modules_path), recursive=True)
                self.file_observer.start()
                log_module_event("hot_reload", "watcher_started", {"path": str(modules_path)})
            else:
                log_module_event("hot_reload", "watcher_skipped", {"reason": "No modules directory found"})
        except Exception as e:
            log_module_event("hot_reload", "watcher_failed", {"error": str(e)})
    
    # Dynamic Module Management Methods
    
    async def enable_module(self, module_name: str) -> bool:
        """Enable a module"""
        try:
            # Update the manifest status
            success = await module_config_manager.update_module_status(module_name, True)
            if not success:
                return False
            
            # Update local config
            if module_name in self.module_configs:
                self.module_configs[module_name].enabled = True
            
            # Load the module if not already loaded
            if module_name not in self.modules:
                config = self.module_configs.get(module_name)
                if config:
                    await self._load_module(module_name, config)
            
            log_module_event(module_name, "enabled", {"success": True})
            return True
            
        except Exception as e:
            log_module_event(module_name, "enable_failed", {"error": str(e)})
            return False
    
    async def disable_module(self, module_name: str) -> bool:
        """Disable a module"""
        try:
            # Update the manifest status
            success = await module_config_manager.update_module_status(module_name, False)
            if not success:
                return False
            
            # Update local config
            if module_name in self.module_configs:
                self.module_configs[module_name].enabled = False
            
            # Unload the module if loaded
            if module_name in self.modules:
                await self.unload_module(module_name)
            
            log_module_event(module_name, "disabled", {"success": True})
            return True
            
        except Exception as e:
            log_module_event(module_name, "disable_failed", {"error": str(e)})
            return False
    
    def get_module_info(self, module_name: str) -> Optional[Dict]:
        """Get comprehensive module information"""
        manifest = module_config_manager.get_module_manifest(module_name)
        if not manifest:
            return None
        
        config = self.module_configs.get(module_name)
        is_loaded = self.is_module_loaded(module_name)
        
        return {
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "author": manifest.author,
            "category": manifest.category,
            "enabled": config.enabled if config else manifest.enabled,
            "loaded": is_loaded,
            "dependencies": manifest.dependencies,
            "optional_dependencies": manifest.optional_dependencies,
            "provides": manifest.provides,
            "consumes": manifest.consumes,
            "endpoints": manifest.endpoints,
            "workflow_steps": manifest.workflow_steps,
            "permissions": manifest.permissions,
            "ui_config": manifest.ui_config,
            "has_schema": module_config_manager.get_module_schema(module_name) is not None,
            "current_config": module_config_manager.get_module_config(module_name)
        }
    
    def list_all_modules(self) -> List[Dict]:
        """List all discovered modules with their information"""
        modules = []
        for name in module_config_manager.manifests.keys():
            module_info = self.get_module_info(name)
            if module_info:
                modules.append(module_info)
        return modules
    
    async def update_module_config(self, module_name: str, config: Dict) -> bool:
        """Update module configuration"""
        try:
            # Validate and save the configuration
            success = await module_config_manager.save_module_config(module_name, config)
            if not success:
                return False
            
            # Update local config
            if module_name in self.module_configs:
                self.module_configs[module_name].config = config
            
            # Reload the module if it's currently loaded
            if self.is_module_loaded(module_name):
                await self.reload_module(module_name)
            
            log_module_event(module_name, "config_updated", {"success": True})
            return True
            
        except Exception as e:
            log_module_event(module_name, "config_update_failed", {"error": str(e)})
            return False
    
    def get_workflow_steps(self) -> Dict[str, List[Dict]]:
        """Get all available workflow steps from modules"""
        return module_config_manager.get_workflow_steps()
    
    async def get_module_health(self, module_name: str) -> Dict:
        """Get module health status"""
        manifest = module_config_manager.get_module_manifest(module_name)
        if not manifest:
            return {"status": "unknown", "message": "Module not found"}
        
        is_loaded = self.is_module_loaded(module_name)
        module = self.get_module(module_name) if is_loaded else None
        
        health = {
            "status": "healthy" if is_loaded else "stopped",
            "loaded": is_loaded,
            "enabled": manifest.enabled,
            "dependencies_met": self._check_dependencies(module_name),
            "last_loaded": None,
            "error": None
        }
        
        # Check if module has custom health check
        if module and hasattr(module, 'get_health'):
            try:
                custom_health = await module.get_health()
                health.update(custom_health)
            except Exception as e:
                health["status"] = "error"
                health["error"] = str(e)
        
        return health
    
    def _check_dependencies(self, module_name: str) -> bool:
        """Check if all module dependencies are met"""
        manifest = module_config_manager.get_module_manifest(module_name)
        if not manifest or not manifest.dependencies:
            return True
        
        for dep in manifest.dependencies:
            if not self.is_module_loaded(dep):
                return False
        
        return True


# Global module manager instance
module_manager = ModuleManager()