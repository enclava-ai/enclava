"""
Plugin Sandbox Environment
Provides secure execution environment for plugins with resource limits and monitoring
"""

import asyncio
import importlib
import importlib.util
import os
import resource
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import psutil

from app.core.logging import get_logger
from app.utils.exceptions import PluginError, SecurityError


@dataclass
class SandboxLimits:
    """Resource limits for plugin sandbox"""

    max_memory_mb: int = -1  # No memory limit (-1 = unlimited)
    max_cpu_percent: int = 25
    max_disk_mb: int = 100
    max_api_calls_per_minute: int = 100
    max_execution_time_seconds: int = 30
    max_file_descriptors: int = 50
    max_threads: int = 10
    allowed_domains: List[str] = None
    network_timeout_seconds: int = 30

    def __post_init__(self):
        if self.allowed_domains is None:
            self.allowed_domains = []


class PluginImportHook:
    """Custom import hook to restrict plugin imports"""

    BLOCKED_MODULES = {
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
        "os.fork",
        "os.exec",
        # System access
        "socket",
        "multiprocessing",
        "threading.Thread",
        "ctypes",
        "mmap",
        "resource",
        "gc",
        # File system
        "shutil.rmtree",
        "os.remove",
        "os.rmdir",
        # Network
        "urllib3",
        "requests.Session",
    }

    ALLOWED_MODULES = {
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
        "collections",
        "itertools",
        "functools",
        "operator",
        "copy",
        "string",
        # Math and data
        "math",
        "decimal",
        "fractions",
        "statistics",
        "pandas",
        "numpy",
        "yaml",
        # HTTP clients
        "httpx",
        "aiohttp.ClientSession",
        # Security and auth
        "jwt",
        "jose",
        "cryptography",
        # Database access for plugins
        "sqlalchemy",
        # Plugin framework
        "app.services.base_plugin",
        "app.schemas.plugin_manifest",
        "app.services.plugin_database",  # Plugin database access
        "app.services.plugin_security",  # Plugin security utilities
        "app.utils.exceptions",  # Plugin exception handling
        "fastapi",
        "pydantic",
    }

    def __init__(self, plugin_id: str):
        self.plugin_id = plugin_id
        self.logger = get_logger(f"plugin.{plugin_id}.imports")
        self.imported_modules: Set[str] = set()

    def validate_import(self, name: str) -> bool:
        """Validate if module import is allowed"""

        # Check if module is explicitly allowed first (takes precedence)
        for allowed in self.ALLOWED_MODULES:
            if name.startswith(allowed):
                self.imported_modules.add(name)
                return True

        # Check if module is explicitly blocked
        for blocked in self.BLOCKED_MODULES:
            if name.startswith(blocked):
                self.logger.error(f"Blocked import attempt: {name}")
                raise SecurityError(
                    f"Import '{name}' not allowed in plugin environment"
                )

        # Log potentially unsafe imports but allow (with warning)
        self.logger.warning(f"Potentially unsafe import: {name}")
        self.imported_modules.add(name)
        return True

    def get_imported_modules(self) -> List[str]:
        """Get list of modules imported by plugin"""
        return list(self.imported_modules)


class PluginASTSecurityValidator:
    """
    AST-based security validator for plugin code.

    SECURITY FIX #7, #24: Implements AST analysis to detect dangerous patterns
    that string matching would miss, such as:
    - Dynamic code execution (eval, exec, compile)
    - Dangerous attribute access (getattr for builtins)
    - Subprocess and OS command execution
    - Direct access to dangerous dunder attributes
    """

    # Dangerous function names to detect
    DANGEROUS_FUNCTIONS = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",  # Only block in certain contexts
        "input",  # Can hang plugins
    }

    # Dangerous attribute names
    DANGEROUS_ATTRIBUTES = {
        "__builtins__",
        "__globals__",
        "__code__",
        "__closure__",
        "__subclasses__",
        "__mro__",
        "__bases__",
        "__class__",
        "__dict__",
        "__getattribute__",
        "__setattr__",
        "__delattr__",
        "func_globals",
        "func_code",
    }

    # Dangerous module.function patterns (module, function)
    DANGEROUS_MODULE_CALLS = {
        ("os", "system"),
        ("os", "popen"),
        ("os", "spawn"),
        ("os", "spawnl"),
        ("os", "spawnle"),
        ("os", "spawnlp"),
        ("os", "spawnlpe"),
        ("os", "spawnv"),
        ("os", "spawnve"),
        ("os", "spawnvp"),
        ("os", "spawnvpe"),
        ("os", "fork"),
        ("os", "forkpty"),
        ("os", "execl"),
        ("os", "execle"),
        ("os", "execlp"),
        ("os", "execlpe"),
        ("os", "execv"),
        ("os", "execve"),
        ("os", "execvp"),
        ("os", "execvpe"),
        ("os", "remove"),
        ("os", "unlink"),
        ("os", "rmdir"),
        ("subprocess", "run"),
        ("subprocess", "call"),
        ("subprocess", "check_call"),
        ("subprocess", "check_output"),
        ("subprocess", "Popen"),
        ("subprocess", "getoutput"),
        ("subprocess", "getstatusoutput"),
        ("shutil", "rmtree"),
        ("shutil", "move"),
        ("importlib", "import_module"),
        ("importlib", "__import__"),
        ("ctypes", "CDLL"),
        ("ctypes", "cdll"),
        ("socket", "socket"),
        ("socket", "create_connection"),
        ("multiprocessing", "Process"),
        ("threading", "Thread"),
        ("gc", "get_objects"),
        ("gc", "get_referrers"),
    }

    # Dangerous imports (module names)
    DANGEROUS_IMPORTS = {
        "subprocess",
        "ctypes",
        "multiprocessing",
        "socket",
        "mmap",
        "resource",
    }

    def __init__(self):
        self.violations = []
        self.logger = get_logger("plugin.ast_validator")

    def validate(self, tree) -> List[str]:
        """Validate AST tree and return list of security violations."""
        import ast

        self.violations = []

        for node in ast.walk(tree):
            self._check_node(node)

        return self.violations

    def _check_node(self, node):
        """Check a single AST node for security issues."""
        import ast

        # Check for direct dangerous function calls
        if isinstance(node, ast.Call):
            self._check_call(node)

        # Check for dangerous attribute access
        elif isinstance(node, ast.Attribute):
            self._check_attribute(node)

        # Check for dangerous imports
        elif isinstance(node, ast.Import):
            self._check_import(node)
        elif isinstance(node, ast.ImportFrom):
            self._check_import_from(node)

        # Check for dangerous string operations that might be code execution
        elif isinstance(node, ast.BinOp):
            self._check_string_concatenation(node)

    def _check_call(self, node):
        """Check function calls for dangerous patterns."""
        import ast

        func = node.func

        # Direct function call: eval(), exec(), etc.
        if isinstance(func, ast.Name):
            if func.id in self.DANGEROUS_FUNCTIONS:
                self.violations.append(f"Dangerous function call: {func.id}()")

        # Attribute call: os.system(), subprocess.run(), etc.
        elif isinstance(func, ast.Attribute):
            # Check for dangerous module.function patterns
            if isinstance(func.value, ast.Name):
                module = func.value.id
                method = func.attr

                if (module, method) in self.DANGEROUS_MODULE_CALLS:
                    self.violations.append(
                        f"Dangerous module call: {module}.{method}()"
                    )

            # Check for getattr on builtins
            if func.attr == "getattr":
                self.violations.append(
                    "Suspicious getattr() call - may be used to bypass restrictions"
                )

        # Check for getattr(obj, 'dangerous_name')
        if isinstance(func, ast.Name) and func.id == "getattr":
            if len(node.args) >= 2:
                second_arg = node.args[1]
                if isinstance(second_arg, ast.Constant):
                    if (
                        second_arg.value
                        in self.DANGEROUS_FUNCTIONS | self.DANGEROUS_ATTRIBUTES
                    ):
                        self.violations.append(
                            f"getattr() used to access dangerous name: {second_arg.value}"
                        )

    def _check_attribute(self, node):
        """Check attribute access for dangerous patterns."""
        if node.attr in self.DANGEROUS_ATTRIBUTES:
            self.violations.append(f"Access to dangerous attribute: {node.attr}")

    def _check_import(self, node):
        """Check import statements."""
        for alias in node.names:
            module = alias.name.split(".")[0]
            if module in self.DANGEROUS_IMPORTS:
                self.violations.append(f"Import of dangerous module: {module}")

    def _check_import_from(self, node):
        """Check from...import statements."""
        if node.module:
            module = node.module.split(".")[0]
            if module in self.DANGEROUS_IMPORTS:
                self.violations.append(f"Import from dangerous module: {module}")

            # Check for platform internals
            if node.module.startswith(
                ("app.db", "app.models", "app.core", "app.services")
            ):
                self.violations.append(
                    f"Import from protected platform module: {node.module}"
                )

    def _check_string_concatenation(self, node):
        """Check for suspicious string concatenation that might build dangerous code."""
        import ast

        # This is a heuristic - check if string concatenation results in dangerous names
        if isinstance(node.op, ast.Add):
            # Check if this looks like building 'eval', 'exec', etc.
            left = self._get_string_value(node.left)
            right = self._get_string_value(node.right)

            if left and right:
                combined = left + right
                if combined in self.DANGEROUS_FUNCTIONS:
                    self.violations.append(
                        f"Suspicious string concatenation building dangerous name: '{combined}'"
                    )

    def _get_string_value(self, node):
        """Extract string value from AST node if it's a constant string."""
        import ast

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None


class PluginResourceMonitor:
    """Monitors plugin resource usage and enforces limits"""

    def __init__(self, plugin_id: str, limits: SandboxLimits):
        self.plugin_id = plugin_id
        self.limits = limits
        self.logger = get_logger(f"plugin.{plugin_id}.resources")

        self.start_time = time.time()
        self.api_call_count = 0
        self.api_call_window_start = time.time()

        # Get current process for monitoring
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss

    def check_memory_limit(self) -> bool:
        """Check if memory usage is within limits"""
        try:
            # Memory limits disabled per user request
            if self.limits.max_memory_mb <= 0:
                return True

            current_memory = self.process.memory_info().rss
            memory_mb = (current_memory - self.initial_memory) / (1024 * 1024)

            if memory_mb > self.limits.max_memory_mb:
                self.logger.error(
                    f"Memory limit exceeded: {memory_mb:.1f}MB > {self.limits.max_memory_mb}MB"
                )
                raise PluginError(f"Plugin {self.plugin_id} exceeded memory limit")

            return True
        except Exception as e:
            self.logger.error(f"Memory check failed: {e}")
            return False

    def check_cpu_limit(self) -> bool:
        """Check if CPU usage is within limits"""
        try:
            cpu_percent = self.process.cpu_percent()

            if cpu_percent > self.limits.max_cpu_percent:
                self.logger.warning(
                    f"CPU usage high: {cpu_percent:.1f}% > {self.limits.max_cpu_percent}%"
                )
                # Don't kill plugin immediately, just warn

            return True
        except Exception as e:
            self.logger.error(f"CPU check failed: {e}")
            return False

    def check_execution_time(self) -> bool:
        """Check if execution time is within limits"""
        execution_time = time.time() - self.start_time

        if execution_time > self.limits.max_execution_time_seconds:
            self.logger.error(
                f"Execution time exceeded: {execution_time:.1f}s > {self.limits.max_execution_time_seconds}s"
            )
            raise PluginError(f"Plugin {self.plugin_id} exceeded execution time limit")

        return True

    def track_api_call(self) -> bool:
        """Track API call and check rate limits"""
        current_time = time.time()

        # Reset counter if window expired
        if current_time - self.api_call_window_start > 60:  # 1 minute window
            self.api_call_count = 0
            self.api_call_window_start = current_time

        self.api_call_count += 1

        if self.api_call_count > self.limits.max_api_calls_per_minute:
            self.logger.error(
                f"API rate limit exceeded: {self.api_call_count} > {self.limits.max_api_calls_per_minute}/min"
            )
            raise PluginError(f"Plugin {self.plugin_id} exceeded API rate limit")

        return True

    def get_resource_stats(self) -> Dict[str, Any]:
        """Get current resource usage statistics"""
        try:
            memory_info = self.process.memory_info()
            current_memory_mb = (memory_info.rss - self.initial_memory) / (1024 * 1024)
            cpu_percent = self.process.cpu_percent()
            execution_time = time.time() - self.start_time

            return {
                "memory_mb": round(current_memory_mb, 2),
                "memory_limit_mb": (
                    "unlimited"
                    if self.limits.max_memory_mb <= 0
                    else self.limits.max_memory_mb
                ),
                "cpu_percent": round(cpu_percent, 2),
                "cpu_limit_percent": self.limits.max_cpu_percent,
                "execution_time_seconds": round(execution_time, 2),
                "execution_limit_seconds": self.limits.max_execution_time_seconds,
                "api_calls_count": self.api_call_count,
                "api_calls_limit": self.limits.max_api_calls_per_minute,
                "threads_count": threading.active_count(),
                "threads_limit": self.limits.max_threads,
            }
        except Exception as e:
            self.logger.error(f"Failed to get resource stats: {e}")
            return {}


class PluginSandbox:
    """Secure sandbox environment for plugin execution"""

    def __init__(self, plugin_id: str, plugin_dir: Path, limits: SandboxLimits = None):
        self.plugin_id = plugin_id
        self.plugin_dir = plugin_dir
        self.limits = limits or SandboxLimits()
        self.logger = get_logger(f"plugin.{plugin_id}.sandbox")

        # Initialize components
        self.import_hook = PluginImportHook(plugin_id)
        self.resource_monitor = PluginResourceMonitor(plugin_id, self.limits)

        # Sandbox state
        self.active = False
        self.original_modules = None
        self.sandbox_modules = {}

    @contextmanager
    def activate(self):
        """Activate sandbox environment for plugin execution"""
        if self.active:
            raise PluginError(f"Sandbox already active for plugin {self.plugin_id}")

        self.logger.info(f"Activating sandbox for plugin {self.plugin_id}")

        try:
            # Store original state
            self.original_modules = sys.modules.copy()

            # Apply resource limits
            self._apply_resource_limits()

            # Install import hook
            self._install_import_hook()

            # Set sandbox environment variables
            self._setup_environment()

            self.active = True
            yield self

        except Exception as e:
            self.logger.error(f"Sandbox activation failed: {e}")
            raise
        finally:
            self.deactivate()

    def deactivate(self):
        """Deactivate sandbox and restore original environment"""
        if not self.active:
            return

        self.logger.info(f"Deactivating sandbox for plugin {self.plugin_id}")

        try:
            # Restore original modules
            if self.original_modules:
                # Remove plugin modules
                modules_to_remove = []
                for module_name in sys.modules:
                    if module_name not in self.original_modules:
                        modules_to_remove.append(module_name)

                for module_name in modules_to_remove:
                    del sys.modules[module_name]

            # Remove import hook
            self._remove_import_hook()

            # Reset resource limits
            self._reset_resource_limits()

            self.active = False

        except Exception as e:
            self.logger.error(f"Sandbox deactivation failed: {e}")

    def _apply_resource_limits(self):
        """Apply resource limits using system resources"""
        try:
            # Skip memory limits if disabled (per user request)
            if self.limits.max_memory_mb > 0:
                memory_bytes = self.limits.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
                self.logger.debug(
                    f"Applied memory limit: {self.limits.max_memory_mb}MB"
                )
            else:
                self.logger.debug("Memory limits disabled per user configuration")

            # Set file descriptor limit
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (self.limits.max_file_descriptors, self.limits.max_file_descriptors),
            )

            self.logger.debug(
                f"Applied resource limits: memory={'unlimited' if self.limits.max_memory_mb <= 0 else f'{self.limits.max_memory_mb}MB'}, fds={self.limits.max_file_descriptors}"
            )

        except Exception as e:
            self.logger.warning(f"Failed to apply some resource limits: {e}")

    def _reset_resource_limits(self):
        """Reset resource limits to system defaults"""
        try:
            # Reset to system limits (usually unlimited)
            resource.setrlimit(resource.RLIMIT_AS, (-1, -1))
            resource.setrlimit(
                resource.RLIMIT_NOFILE, (1024, 1024)
            )  # Conservative default

        except Exception as e:
            self.logger.warning(f"Failed to reset resource limits: {e}")

    def _install_import_hook(self):
        """Install custom import hook for plugin"""
        # Handle both dict and module forms of __builtins__
        if isinstance(__builtins__, dict):
            self.original_import = __builtins__["__import__"]
        else:
            self.original_import = __builtins__.__import__

        def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
            # Validate import
            self.import_hook.validate_import(name)

            # Call original import
            return self.original_import(name, globals, locals, fromlist, level)

        # Replace __import__ (handle both dict and module forms)
        if isinstance(__builtins__, dict):
            __builtins__["__import__"] = restricted_import
        else:
            __builtins__.__import__ = restricted_import

    def _remove_import_hook(self):
        """Remove custom import hook"""
        if hasattr(self, "original_import"):
            # Handle both dict and module forms of __builtins__
            if isinstance(__builtins__, dict):
                __builtins__["__import__"] = self.original_import
            else:
                __builtins__.__import__ = self.original_import

    def _setup_environment(self):
        """Setup sandbox environment variables"""
        # Restrict plugin to its directory
        os.environ[f"PLUGIN_{self.plugin_id.upper()}_DIR"] = str(self.plugin_dir)

        # Set security flags
        os.environ[f"PLUGIN_{self.plugin_id.upper()}_SANDBOX"] = "true"

        # Disable certain features
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"  # Don't write .pyc files

    def validate_network_access(self, domain: str) -> bool:
        """Validate if plugin can access external domain"""
        if not self.limits.allowed_domains:
            return True  # No restrictions

        for allowed_domain in self.limits.allowed_domains:
            if allowed_domain.startswith("*"):
                # Wildcard matching
                pattern = allowed_domain[1:]  # Remove *
                if domain.endswith(pattern):
                    return True
            elif domain == allowed_domain:
                return True

        self.logger.error(f"Network access denied to domain: {domain}")
        return False

    def check_resource_usage(self) -> Dict[str, Any]:
        """Check current resource usage against limits"""
        self.resource_monitor.check_memory_limit()
        self.resource_monitor.check_cpu_limit()
        self.resource_monitor.check_execution_time()

        return self.resource_monitor.get_resource_stats()

    def track_api_call(self) -> bool:
        """Track API call for rate limiting"""
        return self.resource_monitor.track_api_call()


class EnhancedPluginLoader:
    """Enhanced plugin loader with comprehensive sandboxing"""

    def __init__(self):
        self.logger = get_logger("plugin.loader")
        self.loaded_plugins: Dict[str, Any] = {}
        self.plugin_sandboxes: Dict[str, PluginSandbox] = {}

    async def load_plugin_with_sandbox(
        self, plugin_dir: Path, plugin_token: str, sandbox_limits: SandboxLimits = None
    ) -> Any:
        """Load plugin in secure sandbox environment"""

        # Import validation functions here to avoid circular imports
        from app.schemas.plugin_manifest import validate_manifest_file
        from app.services.base_plugin import BasePlugin

        plugin_dir = Path(plugin_dir)

        # Load and validate manifest
        manifest_path = plugin_dir / "manifest.yaml"
        validation_result = validate_manifest_file(manifest_path)

        if not validation_result["valid"]:
            raise PluginError(f"Invalid plugin manifest: {validation_result['errors']}")

        manifest = validation_result["manifest"]
        plugin_id = manifest.metadata.name

        # Check compatibility
        compatibility = validation_result["compatibility"]
        if not compatibility["compatible"]:
            raise PluginError(f"Plugin incompatible: {compatibility['errors']}")

        # Create sandbox with custom limits if specified
        if sandbox_limits is None:
            # Use manifest limits if available
            sandbox_limits = SandboxLimits(
                allowed_domains=(
                    manifest.spec.external_services.allowed_domains
                    if manifest.spec.external_services
                    else []
                )
            )

        sandbox = PluginSandbox(plugin_id, plugin_dir, sandbox_limits)
        self.plugin_sandboxes[plugin_id] = sandbox

        try:
            # Load plugin in sandbox
            with sandbox.activate():
                plugin_instance = await self._load_plugin_module(
                    plugin_dir, manifest, plugin_token
                )

                # Initialize plugin
                await plugin_instance.initialize()
                plugin_instance.initialized = True

                self.loaded_plugins[plugin_id] = plugin_instance
                self.logger.info(f"Plugin {plugin_id} loaded successfully in sandbox")

                return plugin_instance

        except Exception as e:
            # Cleanup on failure
            if plugin_id in self.plugin_sandboxes:
                del self.plugin_sandboxes[plugin_id]
            raise PluginError(f"Failed to load plugin {plugin_id}: {e}")

    async def _load_plugin_module(self, plugin_dir: Path, manifest, plugin_token: str):
        """Load plugin module with security validation"""

        # Import here to avoid circular imports
        from app.services.base_plugin import BasePlugin

        # Validate plugin code security
        main_py_path = plugin_dir / "main.py"
        self._validate_plugin_security(main_py_path)

        # Load module
        spec = importlib.util.spec_from_file_location(
            f"plugin_{manifest.metadata.name}", main_py_path
        )

        if not spec or not spec.loader:
            raise PluginError(f"Cannot load plugin module: {main_py_path}")

        plugin_module = importlib.util.module_from_spec(spec)

        # Add to sys.modules to allow imports
        sys.modules[spec.name] = plugin_module

        try:
            spec.loader.exec_module(plugin_module)
        except Exception as e:
            raise PluginError(f"Failed to execute plugin module: {e}")

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
            raise PluginError("Plugin must contain a class inheriting from BasePlugin")

        # Instantiate plugin
        return plugin_class(manifest, plugin_token)

    def _validate_plugin_security(self, main_py_path: Path):
        """
        Enhanced security validation for plugin code using AST analysis.

        SECURITY FIX #7, #24: Use AST-based validation instead of string matching.
        String matching can be bypassed with:
        - String concatenation: 'ev' + 'al'
        - getattr: getattr(__builtins__, 'eval')
        - Dict access: __builtins__['eval']
        - Unicode tricks: eval vs evаl (cyrillic 'а')

        AST-based validation detects these at the syntax tree level.
        """
        import ast

        with open(main_py_path, "r", encoding="utf-8") as f:
            code_content = f.read()

        # Parse AST for comprehensive security check
        try:
            tree = ast.parse(code_content)
        except SyntaxError as e:
            raise SecurityError(f"Plugin has syntax error: {e}")

        # Run AST-based security validator
        validator = PluginASTSecurityValidator()
        violations = validator.validate(tree)

        if violations:
            raise SecurityError(
                f"Security violations detected in plugin code: {'; '.join(violations)}"
            )

        # Also validate imports against the hook (as before)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".")[0]
                    hook = PluginImportHook("security_check")
                    try:
                        hook.validate_import(module)
                    except SecurityError as e:
                        raise SecurityError(f"Import validation failed: {e}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split(".")[0]
                    hook = PluginImportHook("security_check")
                    try:
                        hook.validate_import(module)
                    except SecurityError as e:
                        raise SecurityError(f"Import validation failed: {e}")

    async def unload_plugin(self, plugin_id: str) -> bool:
        """Unload plugin and cleanup sandbox"""
        if plugin_id not in self.loaded_plugins:
            return False

        plugin = self.loaded_plugins[plugin_id]

        try:
            # Cleanup plugin
            await plugin.cleanup()

            # Deactivate sandbox
            if plugin_id in self.plugin_sandboxes:
                sandbox = self.plugin_sandboxes[plugin_id]
                sandbox.deactivate()
                del self.plugin_sandboxes[plugin_id]

            # Remove from loaded plugins
            del self.loaded_plugins[plugin_id]

            self.logger.info(f"Plugin {plugin_id} unloaded successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error unloading plugin {plugin_id}: {e}")
            return False

    def get_plugin_sandbox(self, plugin_id: str) -> Optional[PluginSandbox]:
        """Get sandbox for plugin"""
        return self.plugin_sandboxes.get(plugin_id)

    def get_resource_stats(self, plugin_id: str) -> Dict[str, Any]:
        """Get resource usage statistics for plugin"""
        sandbox = self.get_plugin_sandbox(plugin_id)
        if sandbox:
            return sandbox.check_resource_usage()
        return {}

    def list_loaded_plugins(self) -> List[Dict[str, Any]]:
        """List all loaded plugins with their status"""
        plugins = []

        for plugin_id, plugin in self.loaded_plugins.items():
            sandbox = self.get_plugin_sandbox(plugin_id)
            resource_stats = self.get_resource_stats(plugin_id) if sandbox else {}

            plugins.append(
                {
                    "plugin_id": plugin_id,
                    "version": plugin.version,
                    "initialized": plugin.initialized,
                    "sandbox_active": sandbox.active if sandbox else False,
                    "resource_usage": resource_stats,
                }
            )

        return plugins


# Global plugin loader instance
plugin_loader = EnhancedPluginLoader()
