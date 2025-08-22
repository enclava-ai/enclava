"""
Plugin Registry and Discovery System
Handles plugin installation, updates, discovery, and marketplace functionality
"""
import asyncio
import os
import shutil
import tempfile
import zipfile
import aiohttp
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_
import hashlib
import json
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.exceptions import InvalidSignature

from app.core.config import settings
from app.core.logging import get_logger
from app.models.plugin import Plugin, PluginConfiguration, PluginAuditLog
from app.models.user import User
from app.db.database import get_db
from app.schemas.plugin_manifest import PluginManifestValidator, validate_manifest_file
from app.services.plugin_sandbox import plugin_loader
from app.services.plugin_database import plugin_db_manager, plugin_migration_manager
from app.utils.exceptions import PluginError, SecurityError, ValidationError


logger = get_logger("plugin.registry")


class PluginRepositoryClient:
    """Client for interacting with plugin repositories"""
    
    def __init__(self, repository_url: str = None):
        self.repository_url = repository_url or settings.PLUGIN_REPOSITORY_URL
        self.timeout = 30
    
    async def search_plugins(self, query: str, tags: List[str] = None, 
                           limit: int = 20) -> List[Dict[str, Any]]:
        """Search for plugins in repository"""
        try:
            # Try connecting to the repository
            params = {
                "q": query,
                "limit": limit
            }
            
            if tags:
                params["tags"] = ",".join(tags)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.repository_url}/api/plugins/search",
                    params=params,
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("plugins", [])
                    else:
                        logger.error(f"Plugin search failed: {response.status}")
                        # Repository unavailable, return empty list
                        return []
                        
        except Exception as e:
            logger.error(f"Plugin search error: {e}")
            # Repository unavailable, return empty list
            return []
    
    
    async def get_plugin_info(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a plugin"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.repository_url}/api/plugins/{plugin_id}",
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        return None
                    else:
                        logger.error(f"Failed to get plugin info for {plugin_id}: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting plugin info for {plugin_id}: {e}")
            return None
    
    async def download_plugin(self, plugin_id: str, version: str, 
                            download_path: Path) -> bool:
        """Download plugin package from repository"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.repository_url}/api/plugins/{plugin_id}/download/{version}",
                    timeout=60  # Longer timeout for downloads
                ) as response:
                    if response.status == 200:
                        with open(download_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        return True
                    else:
                        logger.error(f"Plugin download failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Plugin download error: {e}")
            return False
    
    async def verify_plugin_signature(self, plugin_path: Path, 
                                    signature: str) -> bool:
        """Verify plugin package signature using RSA digital signatures"""
        try:
            # Calculate file hash
            with open(plugin_path, 'rb') as f:
                file_content = f.read()
                file_hash = hashlib.sha256(file_content).digest()
            
            # Load platform public key for verification
            public_key = self._get_platform_public_key()
            if not public_key:
                logger.error("No platform public key available for signature verification")
                return False
            
            # Decode base64 signature
            try:
                signature_bytes = base64.b64decode(signature)
            except Exception as e:
                logger.error(f"Invalid signature format: {e}")
                return False
            
            # Verify RSA signature
            try:
                public_key.verify(
                    signature_bytes,
                    file_hash,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                
                logger.info(f"Plugin signature verified successfully for {plugin_path.name}")
                return True
                
            except InvalidSignature:
                logger.error(f"Invalid signature for plugin {plugin_path.name}")
                return False
            
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    def _get_platform_public_key(self):
        """Get platform public key for signature verification"""
        try:
            # Try to load from environment variable first
            public_key_pem = os.environ.get('PLUGIN_SIGNING_PUBLIC_KEY')
            
            if public_key_pem:
                public_key = serialization.load_pem_public_key(public_key_pem.encode())
                return public_key
            
            # Fall back to file-based public key
            public_key_path = Path("/data/plugin_keys/public_key.pem")
            if public_key_path.exists():
                with open(public_key_path, 'rb') as f:
                    public_key = serialization.load_pem_public_key(f.read())
                return public_key
            
            # Generate development key pair if none exists
            return self._generate_development_key_pair()
            
        except Exception as e:
            logger.error(f"Failed to load platform public key: {e}")
            return None
    
    def _generate_development_key_pair(self):
        """Generate development key pair for testing (NOT for production)"""
        try:
            logger.warning("Generating development key pair for plugin signing - NOT for production use!")
            
            # Generate RSA key pair
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            public_key = private_key.public_key()
            
            # Save keys to secure location
            keys_dir = Path("/data/plugin_keys")
            keys_dir.mkdir(parents=True, exist_ok=True)
            
            # Save private key (for development signing)
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            private_key_path = keys_dir / "private_key.pem"
            with open(private_key_path, 'wb') as f:
                f.write(private_pem)
            
            # Save public key
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            public_key_path = keys_dir / "public_key.pem"
            with open(public_key_path, 'wb') as f:
                f.write(public_pem)
            
            # Log the public key for production configuration
            public_key_b64 = base64.b64encode(public_pem).decode()
            logger.warning(
                f"Generated development keys. For production, set PLUGIN_SIGNING_PUBLIC_KEY environment variable to: "
                f"{public_key_b64}"
            )
            
            return public_key
            
        except Exception as e:
            logger.error(f"Failed to generate development key pair: {e}")
            return None
    
    async def sign_plugin_package(self, plugin_path: Path) -> Optional[str]:
        """Sign plugin package (for development/testing)"""
        try:
            # This method is for development use only
            private_key_path = Path("/data/plugin_keys/private_key.pem")
            if not private_key_path.exists():
                logger.error("No private key available for signing")
                return None
            
            # Load private key
            with open(private_key_path, 'rb') as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None
                )
            
            # Calculate file hash
            with open(plugin_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).digest()
            
            # Sign the hash
            signature = private_key.sign(
                file_hash,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Return base64-encoded signature
            return base64.b64encode(signature).decode()
            
        except Exception as e:
            logger.error(f"Failed to sign plugin package: {e}")
            return None


class PluginInstaller:
    """Handles plugin installation and updates"""
    
    def __init__(self):
        self.plugins_dir = Path(settings.PLUGINS_DIR or "/plugins")
        self.plugins_dir.mkdir(exist_ok=True)
        self.temp_dir = Path(tempfile.gettempdir()) / "enclava_plugins"
        self.temp_dir.mkdir(exist_ok=True)
    
    async def install_plugin_from_file(self, plugin_file: Path, user_id: str, 
                                     db: AsyncSession) -> Dict[str, Any]:
        """Install plugin from uploaded file"""
        try:
            # Extract plugin to temporary directory
            temp_extract_dir = self.temp_dir / f"extract_{int(asyncio.get_event_loop().time())}"
            temp_extract_dir.mkdir(exist_ok=True)
            
            try:
                # Extract ZIP file
                with zipfile.ZipFile(plugin_file, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_dir)
                
                # Find and validate manifest
                manifest_path = self._find_manifest(temp_extract_dir)
                if not manifest_path:
                    raise ValidationError("No valid manifest.yaml found in plugin package")
                
                validation_result = validate_manifest_file(manifest_path)
                if not validation_result["valid"]:
                    raise ValidationError(f"Invalid plugin manifest: {validation_result['errors']}")
                
                manifest = validation_result["manifest"]
                plugin_id = manifest.metadata.name
                
                # Check if plugin already exists
                from sqlalchemy import select
                stmt = select(Plugin).where(Plugin.id == plugin_id)
                result = await db.execute(stmt)
                existing_plugin = result.scalar_one_or_none()
                if existing_plugin:
                    return await self._update_existing_plugin(
                        existing_plugin, temp_extract_dir, manifest, user_id, db
                    )
                else:
                    return await self._install_new_plugin(
                        temp_extract_dir, manifest, user_id, db
                    )
                    
            finally:
                # Cleanup temporary directory
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
                
        except Exception as e:
            logger.error(f"Plugin installation failed: {e}")
            raise PluginError(f"Installation failed: {e}")
    
    async def install_plugin_from_repository(self, plugin_id: str, version: str,
                                           user_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Install plugin from repository"""
        try:
            # Download plugin
            repo_client = PluginRepositoryClient()
            
            # Get plugin info
            plugin_info = await repo_client.get_plugin_info(plugin_id)
            if not plugin_info:
                raise PluginError(f"Plugin {plugin_id} not found in repository")
            
            # Download plugin package
            download_path = self.temp_dir / f"{plugin_id}_{version}.zip"
            success = await repo_client.download_plugin(plugin_id, version, download_path)
            if not success:
                raise PluginError(f"Failed to download plugin {plugin_id}")
            
            try:
                # Verify signature if available
                signature = plugin_info.get("signature")
                if signature:
                    verified = await repo_client.verify_plugin_signature(download_path, signature)
                    if not verified:
                        raise SecurityError("Plugin signature verification failed")
                
                # Install from downloaded file
                return await self.install_plugin_from_file(download_path, user_id, db)
                
            finally:
                # Cleanup downloaded file
                download_path.unlink(missing_ok=True)
                
        except Exception as e:
            logger.error(f"Repository installation failed: {e}")
            raise PluginError(f"Repository installation failed: {e}")
    
    async def uninstall_plugin(self, plugin_id: str, user_id: str, 
                              db: AsyncSession, keep_data: bool = True) -> Dict[str, Any]:
        """Uninstall plugin"""
        try:
            # Get plugin
            from sqlalchemy import select
            stmt = select(Plugin).where(Plugin.id == plugin_id)
            result = await db.execute(stmt)
            plugin = result.scalar_one_or_none()
            if not plugin:
                raise PluginError(f"Plugin {plugin_id} not found")
            
            # Check if user can uninstall
            if plugin.installed_by_user_id != user_id:
                # Check if user has admin permissions
                user_stmt = select(User).where(User.id == user_id)
                user_result = await db.execute(user_stmt)
                user = user_result.scalar_one_or_none()
                
                if not user:
                    raise PluginError(f"User {user_id} not found")
                
                # Check if user is admin
                if not (hasattr(user, 'is_admin') and user.is_admin):
                    raise PluginError("Insufficient permissions to uninstall plugin. Only plugin owner or admin can uninstall.")
                
                logger.info(f"Admin user {user_id} uninstalling plugin {plugin_id} installed by {plugin.installed_by_user_id}")
            
            # Unload plugin if running
            if plugin_id in plugin_loader.loaded_plugins:
                await plugin_loader.unload_plugin(plugin_id)
            
            # Backup data if requested
            backup_path = None
            if keep_data:
                backup_path = await plugin_db_manager.backup_plugin_data(plugin_id)
            
            # Delete database schema if not keeping data
            if not keep_data:
                await plugin_db_manager.delete_plugin_schema(plugin_id)
            
            # Remove plugin files
            plugin_dir = self.plugins_dir / plugin_id
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
            
            # Update database
            plugin.status = "uninstalled"
            plugin.updated_at = datetime.now(timezone.utc)
            
            # Log uninstall
            audit_log = PluginAuditLog(
                plugin_id=plugin_id,
                user_id=user_id,
                action="uninstall",
                details={
                    "keep_data": keep_data,
                    "backup_path": backup_path
                }
            )
            db.add(audit_log)
            await db.commit()
            
            logger.info(f"Plugin {plugin_id} uninstalled successfully")
            
            return {
                "status": "uninstalled",
                "plugin_id": plugin_id,
                "backup_path": backup_path,
                "data_kept": keep_data
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Plugin uninstall failed: {e}")
            raise PluginError(f"Uninstall failed: {e}")
    
    def _find_manifest(self, plugin_dir: Path) -> Optional[Path]:
        """Find manifest.yaml file in plugin directory"""
        # Look for manifest.yaml in root
        manifest_path = plugin_dir / "manifest.yaml"
        if manifest_path.exists():
            return manifest_path
        
        # Look for manifest.yaml in subdirectories
        for subdir in plugin_dir.iterdir():
            if subdir.is_dir():
                manifest_path = subdir / "manifest.yaml"
                if manifest_path.exists():
                    return manifest_path
        
        return None
    
    async def _install_new_plugin(self, temp_dir: Path, manifest, 
                                user_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Install new plugin"""
        plugin_id = manifest.metadata.name
        
        # Create plugin directory
        plugin_dir = self.plugins_dir / plugin_id
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        
        # Copy plugin files
        shutil.copytree(temp_dir, plugin_dir)
        
        # Create database record
        plugin = Plugin(
            id=plugin_id,
            name=manifest.metadata.name,
            version=manifest.metadata.version,
            description=manifest.metadata.description,
            author=manifest.metadata.author,
            manifest_data=manifest.dict(),
            status="installed",
            installed_by_user_id=user_id,
            plugin_dir=str(plugin_dir)
        )
        
        db.add(plugin)
        db.flush()  # Get plugin ID
        
        # Create database schema
        await plugin_db_manager.create_plugin_schema(plugin_id, manifest.dict())
        
        # Create migration environment
        await plugin_migration_manager.create_migration_environment(plugin_id, plugin_dir)
        
        # Log installation
        audit_log = PluginAuditLog(
            plugin_id=plugin_id,
            user_id=user_id,
            action="install",
            details={
                "version": manifest.metadata.version,
                "source": "file_upload"
            }
        )
        db.add(audit_log)
        db.commit()
        
        logger.info(f"New plugin {plugin_id} v{manifest.metadata.version} installed")
        
        return {
            "status": "installed",
            "plugin_id": plugin_id,
            "version": manifest.metadata.version,
            "new_installation": True
        }
    
    async def _update_existing_plugin(self, existing_plugin: Plugin, temp_dir: Path,
                                    manifest, user_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Update existing plugin"""
        plugin_id = manifest.metadata.name
        old_version = existing_plugin.version
        new_version = manifest.metadata.version
        
        # Version check
        if old_version == new_version:
            raise PluginError(f"Plugin {plugin_id} v{new_version} is already installed")
        
        # Backup current version
        backup_dir = self.plugins_dir / f"{plugin_id}_backup_{old_version}"
        plugin_dir = self.plugins_dir / plugin_id
        
        if plugin_dir.exists():
            shutil.copytree(plugin_dir, backup_dir)
        
        try:
            # Unload plugin if running
            if plugin_id in plugin_loader.loaded_plugins:
                await plugin_loader.unload_plugin(plugin_id)
            
            # Update plugin files
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
            shutil.copytree(temp_dir, plugin_dir)
            
            # Run migrations
            await plugin_migration_manager.run_plugin_migrations(plugin_id, plugin_dir)
            
            # Update database record
            existing_plugin.version = new_version
            existing_plugin.description = manifest.metadata.description
            existing_plugin.manifest_data = manifest.dict()
            existing_plugin.updated_at = datetime.now(timezone.utc)
            
            # Log update
            audit_log = PluginAuditLog(
                plugin_id=plugin_id,
                user_id=user_id,
                action="update",
                details={
                    "old_version": old_version,
                    "new_version": new_version,
                    "backup_dir": str(backup_dir)
                }
            )
            db.add(audit_log)
            await db.commit()
            
            # Cleanup backup after successful update
            shutil.rmtree(backup_dir, ignore_errors=True)
            
            logger.info(f"Plugin {plugin_id} updated from v{old_version} to v{new_version}")
            
            return {
                "status": "updated",
                "plugin_id": plugin_id,
                "old_version": old_version,
                "new_version": new_version,
                "new_installation": False
            }
            
        except Exception as e:
            # Restore backup on failure
            if backup_dir.exists():
                if plugin_dir.exists():
                    shutil.rmtree(plugin_dir)
                shutil.copytree(backup_dir, plugin_dir)
                shutil.rmtree(backup_dir, ignore_errors=True)
            
            await db.rollback()
            raise PluginError(f"Plugin update failed: {e}")


class PluginDiscoveryService:
    """Handles plugin discovery and marketplace functionality"""
    
    def __init__(self):
        self.repo_client = PluginRepositoryClient()
    
    async def search_available_plugins(self, query: str = "", tags: List[str] = None,
                                     category: str = None, limit: int = 20, db: AsyncSession = None) -> List[Dict[str, Any]]:
        """Search for available plugins"""
        try:
            # Search repository
            plugins = await self.repo_client.search_plugins(query, tags, limit)
            
            # Add local installation status
            if db is not None:
                for plugin in plugins:
                    stmt = select(Plugin).where(Plugin.id == plugin["id"])
                    result = await db.execute(stmt)
                    local_plugin = result.scalar_one_or_none()
                    
                    if local_plugin:
                        plugin["local_status"] = {
                            "installed": True,
                            "version": local_plugin.version,
                            "status": local_plugin.status,
                            "update_available": plugin["version"] != local_plugin.version
                        }
                    else:
                        plugin["local_status"] = {
                            "installed": False,
                            "update_available": False
                        }
            else:
                # If no database session provided, mark all as not installed
                for plugin in plugins:
                    plugin["local_status"] = {
                        "installed": False,
                        "update_available": False
                    }
                
            return plugins
                
        except Exception as e:
            logger.error(f"Plugin discovery error: {e}")
            return []
    
    async def get_installed_plugins(self, user_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
        """Get list of installed plugins for user"""
        try:
            # Get all installed plugins (for now, show all plugins to all users)
            # TODO: Implement proper user-based plugin visibility/permissions
            from sqlalchemy import select
            
            stmt = select(Plugin).where(
                Plugin.status.in_(["installed", "enabled", "disabled"])
            )
            result = await db.execute(stmt)
            installed_plugins = result.scalars().all()
            
            # If no plugins installed, return empty list
            if not installed_plugins:
                return []
            
            plugin_list = []
            for plugin in installed_plugins:
                try:
                    # Get runtime status safely
                    plugin_id = str(plugin.id)  # Ensure string conversion
                    loaded = plugin_id in plugin_loader.loaded_plugins
                    health_status = {}
                    resource_stats = {}
                    
                    if loaded:
                        try:
                            plugin_instance = plugin_loader.loaded_plugins[plugin_id]
                            health_status = await plugin_instance.health_check()
                            resource_stats = plugin_loader.get_resource_stats(plugin_id)
                        except Exception as e:
                            logger.warning(f"Failed to get runtime info for plugin {plugin_id}: {e}")
                    
                    # Get database stats safely
                    db_stats = {}
                    try:
                        db_stats = await plugin_db_manager.get_plugin_database_stats(plugin_id)
                    except Exception as e:
                        logger.warning(f"Failed to get database stats for plugin {plugin_id}: {e}")
                    
                    plugin_list.append({
                        "id": plugin_id,
                        "name": plugin.name or "Unknown",
                        "version": plugin.version or "Unknown",
                        "description": plugin.description or "",
                        "author": plugin.author or "Unknown",
                        "status": plugin.status,
                        "loaded": loaded,
                        "health": health_status,
                        "resource_usage": resource_stats,
                        "database_stats": db_stats,
                        "installed_at": plugin.installed_at.isoformat() if plugin.installed_at else None,
                        "updated_at": plugin.last_updated_at.isoformat() if plugin.last_updated_at else None
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing plugin {getattr(plugin, 'id', 'unknown')}: {e}")
                    continue
            
            return plugin_list
            
        except Exception as e:
            logger.error(f"Error getting installed plugins: {e}")
            return []
    
    
    async def get_plugin_updates(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Check for available plugin updates"""
        try:
            from sqlalchemy import select
            stmt = select(Plugin).where(
                Plugin.status.in_(["installed", "enabled"])
            )
            result = await db.execute(stmt)
            installed_plugins = result.scalars().all()
            
            updates = []
            for plugin in installed_plugins:
                try:
                    # Check repository for newer version
                    plugin_info = await self.repo_client.get_plugin_info(plugin.id)
                    if plugin_info and plugin_info["version"] != plugin.version:
                        updates.append({
                            "plugin_id": plugin.id,
                            "name": plugin.name,
                            "current_version": plugin.version,
                            "available_version": plugin_info["version"],
                            "description": plugin_info.get("description", ""),
                            "changelog": plugin_info.get("changelog", ""),
                            "update_available": True
                        })
                        
                except Exception as e:
                    logger.warning(f"Failed to check updates for {plugin.id}: {e}")
                    continue
            
            return updates
            
        except Exception as e:
            logger.error(f"Error checking plugin updates: {e}")
            return []
    
    async def get_plugin_categories(self) -> List[Dict[str, Any]]:
        """Get available plugin categories"""
        try:
            # TODO: Implement category discovery from repository
            default_categories = [
                {
                    "id": "integrations",
                    "name": "Integrations", 
                    "description": "Third-party service integrations"
                },
                {
                    "id": "ai-tools",
                    "name": "AI Tools",
                    "description": "AI and machine learning tools"
                },
                {
                    "id": "productivity", 
                    "name": "Productivity",
                    "description": "Productivity and workflow tools"
                },
                {
                    "id": "analytics",
                    "name": "Analytics",
                    "description": "Data analytics and reporting"
                },
                {
                    "id": "communication",
                    "name": "Communication", 
                    "description": "Communication and collaboration tools"
                },
                {
                    "id": "security",
                    "name": "Security",
                    "description": "Security and compliance tools"
                }
            ]
            
            return default_categories
            
        except Exception as e:
            logger.error(f"Error getting plugin categories: {e}")
            return []


# Global instances
plugin_installer = PluginInstaller()
plugin_discovery = PluginDiscoveryService()
