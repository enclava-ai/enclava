"""
Plugin Auto-Discovery Service
Automatically discovers and registers plugins from the /plugins directory on startup
"""

import asyncio
import os
import uuid
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.plugin import Plugin
from app.db.database import SessionLocal
from app.schemas.plugin_manifest import validate_manifest_file
from app.services.plugin_database import plugin_db_manager
from app.services.plugin_sandbox import plugin_loader
from app.utils.exceptions import PluginError

logger = get_logger("plugin.autodiscovery")


class PluginAutoDiscovery:
    """Service for automatically discovering and registering plugins"""

    def __init__(self, plugins_dir: str = None):
        self.plugins_dir = Path(plugins_dir or settings.PLUGINS_DIR)
        self.discovered_plugins: Dict[str, Dict[str, Any]] = {}

    async def scan_plugins_directory(self) -> List[Dict[str, Any]]:
        """Scan plugins directory for valid plugin manifests"""
        logger.info(f"Scanning plugins directory: {self.plugins_dir}")

        if not self.plugins_dir.exists():
            logger.warning(f"Plugins directory does not exist: {self.plugins_dir}")
            return []

        discovered = []

        try:
            for item in self.plugins_dir.iterdir():
                if item.is_dir():
                    plugin_info = await self._discover_plugin(item)
                    if plugin_info:
                        discovered.append(plugin_info)
                        self.discovered_plugins[plugin_info["slug"]] = plugin_info

            logger.info(f"Discovered {len(discovered)} plugins in directory")
            return discovered

        except Exception as e:
            logger.error(f"Error scanning plugins directory: {e}")
            return []

    async def _discover_plugin(self, plugin_path: Path) -> Optional[Dict[str, Any]]:
        """Discover and validate a single plugin"""
        try:
            manifest_path = plugin_path / "manifest.yaml"

            if not manifest_path.exists():
                logger.debug(f"No manifest found in {plugin_path.name}")
                return None

            # Validate manifest
            validation_result = validate_manifest_file(manifest_path)

            if not validation_result["valid"]:
                logger.warning(
                    f"Invalid manifest for plugin {plugin_path.name}: {validation_result['errors']}"
                )
                return None

            manifest = validation_result["manifest"]

            # Check if main.py exists
            main_py_path = plugin_path / "main.py"
            if not main_py_path.exists():
                logger.warning(f"No main.py found for plugin {plugin_path.name}")
                return None

            # Generate hashes for plugin integrity
            manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            package_hash = hashlib.sha256(str(plugin_path).encode()).hexdigest()

            # Convert manifest to JSON-serializable format
            import json

            manifest_dict = json.loads(manifest.json())

            plugin_info = {
                "slug": manifest.metadata.name,  # Use slug for string identifier
                "name": manifest.metadata.name,
                "display_name": manifest.metadata.description,
                "version": manifest.metadata.version,
                "description": manifest.metadata.description,
                "author": manifest.metadata.author,
                "manifest_data": manifest_dict,  # Use JSON-serialized version
                "plugin_path": str(plugin_path),
                "manifest_path": str(manifest_path),
                "main_py_path": str(main_py_path),
                "manifest_hash": manifest_hash,
                "package_hash": package_hash,
                "discovered_at": datetime.now(timezone.utc),
            }

            logger.info(
                f"Discovered plugin: {manifest.metadata.name} v{manifest.metadata.version}"
            )
            return plugin_info

        except Exception as e:
            logger.error(f"Error discovering plugin at {plugin_path}: {e}")
            return None

    async def register_discovered_plugins(self) -> Dict[str, bool]:
        """Register all discovered plugins in the database"""
        logger.info("Registering discovered plugins in database...")

        registration_results = {}
        db = SessionLocal()

        try:
            for plugin_slug, plugin_info in self.discovered_plugins.items():
                try:
                    success = await self._register_single_plugin(db, plugin_info)
                    registration_results[plugin_slug] = success

                    if success:
                        logger.info(f"Plugin {plugin_slug} registered successfully")
                    else:
                        logger.warning(f"Failed to register plugin {plugin_slug}")

                except Exception as e:
                    logger.error(f"Error registering plugin {plugin_slug}: {e}")
                    registration_results[plugin_slug] = False

        finally:
            db.close()

        successful_registrations = sum(
            1 for success in registration_results.values() if success
        )
        logger.info(
            f"Plugin registration complete: {successful_registrations}/{len(registration_results)} successful"
        )

        return registration_results

    async def _register_single_plugin(
        self, db: Session, plugin_info: Dict[str, Any]
    ) -> bool:
        """Register a single plugin in the database"""
        try:
            plugin_slug = plugin_info["slug"]

            # Check if plugin already exists by slug
            existing_plugin = (
                db.query(Plugin).filter(Plugin.slug == plugin_slug).first()
            )

            if existing_plugin:
                # Update existing plugin if version is different
                if existing_plugin.version != plugin_info["version"]:
                    logger.info(
                        f"Updating plugin {plugin_slug}: {existing_plugin.version} -> {plugin_info['version']}"
                    )

                    existing_plugin.version = plugin_info["version"]
                    existing_plugin.description = plugin_info["description"]
                    existing_plugin.author = plugin_info["author"]
                    existing_plugin.manifest_data = plugin_info["manifest_data"]
                    existing_plugin.package_path = plugin_info["plugin_path"]
                    existing_plugin.manifest_hash = plugin_info["manifest_hash"]
                    existing_plugin.package_hash = plugin_info["package_hash"]
                    existing_plugin.last_updated_at = datetime.now(timezone.utc)

                    db.commit()

                    # Update plugin schema
                    await self._setup_plugin_database(plugin_slug, plugin_info)
                    return True
                else:
                    logger.debug(f"Plugin {plugin_slug} already up to date")
                    return True

            else:
                # Create new plugin record
                logger.info(f"Installing new plugin {plugin_slug}")

                plugin = Plugin(
                    id=uuid.uuid4(),  # Generate UUID for primary key
                    name=plugin_info["name"],
                    slug=plugin_info["slug"],
                    display_name=plugin_info["display_name"],
                    version=plugin_info["version"],
                    description=plugin_info["description"],
                    author=plugin_info["author"],
                    manifest_data=plugin_info["manifest_data"],
                    package_path=plugin_info["plugin_path"],
                    manifest_hash=plugin_info["manifest_hash"],
                    package_hash=plugin_info["package_hash"],
                    status="installed",
                    installed_by_user_id=1,  # System installation
                    auto_enable=True,  # Auto-enable discovered plugins
                )

                db.add(plugin)
                db.commit()

                # Setup plugin database schema
                await self._setup_plugin_database(plugin_slug, plugin_info)

                logger.info(f"Plugin {plugin_slug} installed successfully")
                return True

        except Exception as e:
            db.rollback()
            logger.error(
                f"Database error registering plugin {plugin_info['slug']}: {e}"
            )
            return False

    async def _setup_plugin_database(
        self, plugin_id: str, plugin_info: Dict[str, Any]
    ) -> bool:
        """Setup database schema for plugin"""
        try:
            manifest_data = plugin_info["manifest_data"]

            # Create plugin database schema if specified
            if "database" in manifest_data.get("spec", {}):
                logger.info(f"Creating database schema for plugin {plugin_id}")
                await plugin_db_manager.create_plugin_schema(plugin_id, manifest_data)
                logger.info(f"Database schema created for plugin {plugin_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to setup database for plugin {plugin_id}: {e}")
            return False

    async def load_discovered_plugins(self) -> Dict[str, bool]:
        """Load all discovered plugins into the plugin sandbox"""
        logger.info("Loading discovered plugins into sandbox...")

        loading_results = {}

        for plugin_slug, plugin_info in self.discovered_plugins.items():
            try:
                # Load plugin into sandbox using the correct method
                plugin_dir = Path(plugin_info["plugin_path"])
                plugin_token = (
                    f"plugin_{plugin_slug}_token"  # Generate a token for the plugin
                )

                plugin_instance = await plugin_loader.load_plugin_with_sandbox(
                    plugin_dir, plugin_token
                )

                if plugin_instance:
                    loading_results[plugin_slug] = True
                    logger.info(f"Plugin {plugin_slug} loaded successfully")
                else:
                    loading_results[plugin_slug] = False
                    logger.warning(f"Failed to load plugin {plugin_slug}")

            except Exception as e:
                logger.error(f"Error loading plugin {plugin_slug}: {e}")
                loading_results[plugin_slug] = False

        successful_loads = sum(1 for success in loading_results.values() if success)
        logger.info(
            f"Plugin loading complete: {successful_loads}/{len(loading_results)} successful"
        )

        return loading_results

    async def auto_discover_and_register(self) -> Dict[str, Any]:
        """Complete auto-discovery workflow: scan, register, and load plugins"""
        logger.info("Starting plugin auto-discovery...")

        results = {
            "discovered": [],
            "registered": {},
            "loaded": {},
            "summary": {
                "total_discovered": 0,
                "successful_registrations": 0,
                "successful_loads": 0,
            },
        }

        try:
            # Step 1: Scan directory for plugins
            discovered_plugins = await self.scan_plugins_directory()
            results["discovered"] = [p["slug"] for p in discovered_plugins]
            results["summary"]["total_discovered"] = len(discovered_plugins)

            if not discovered_plugins:
                logger.info("No plugins discovered")
                return results

            # Step 2: Register plugins in database
            registration_results = await self.register_discovered_plugins()
            results["registered"] = registration_results
            results["summary"]["successful_registrations"] = sum(
                1 for success in registration_results.values() if success
            )

            # Step 3: Load plugins into sandbox
            loading_results = await self.load_discovered_plugins()
            results["loaded"] = loading_results
            results["summary"]["successful_loads"] = sum(
                1 for success in loading_results.values() if success
            )

            logger.info(
                f"Auto-discovery complete! Discovered: {results['summary']['total_discovered']}, "
                f"Registered: {results['summary']['successful_registrations']}, "
                f"Loaded: {results['summary']['successful_loads']}"
            )

            return results

        except Exception as e:
            logger.error(f"Auto-discovery failed: {e}")
            results["error"] = str(e)
            return results

    def get_discovery_status(self) -> Dict[str, Any]:
        """Get current discovery status"""
        return {
            "plugins_dir": str(self.plugins_dir),
            "plugins_dir_exists": self.plugins_dir.exists(),
            "discovered_plugins": list(self.discovered_plugins.keys()),
            "discovery_count": len(self.discovered_plugins),
            "last_scan": datetime.now(timezone.utc).isoformat(),
        }


# Global auto-discovery service instance
plugin_autodiscovery = PluginAutoDiscovery()


async def initialize_plugin_autodiscovery() -> Dict[str, Any]:
    """Initialize plugin auto-discovery service (called from main.py)"""
    logger.info("Initializing plugin auto-discovery service...")

    try:
        results = await plugin_autodiscovery.auto_discover_and_register()
        logger.info("Plugin auto-discovery service initialized successfully")
        return results

    except Exception as e:
        logger.error(f"Plugin auto-discovery initialization failed: {e}")
        return {
            "error": str(e),
            "summary": {
                "total_discovered": 0,
                "successful_registrations": 0,
                "successful_loads": 0,
            },
        }


# Convenience function for manual plugin discovery
async def discover_plugins_now() -> Dict[str, Any]:
    """Manually trigger plugin discovery (for testing/debugging)"""
    return await plugin_autodiscovery.auto_discover_and_register()
