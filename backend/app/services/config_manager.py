"""
Configuration Management Service - Core App Integration
Provides centralized configuration management with hot-reloading and encryption.
"""
import asyncio
import json
import os
import hashlib
import time
import threading
from typing import Dict, Any, Optional, List, Union, Callable
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from cryptography.fernet import Fernet
import yaml
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ConfigVersion:
    """Configuration version metadata"""
    version: str
    timestamp: datetime
    checksum: str
    author: str
    description: str
    config_data: Dict[str, Any]


@dataclass
class ConfigSchema:
    """Configuration schema definition"""
    name: str
    required_fields: List[str]
    optional_fields: List[str]
    field_types: Dict[str, type]
    validators: Dict[str, Callable]


@dataclass
class ConfigStats:
    """Configuration manager statistics"""
    total_configs: int
    active_watchers: int
    config_versions: int
    encrypted_configs: int
    hot_reloads_performed: int
    validation_errors: int
    last_reload_time: datetime
    uptime: float


class ConfigWatcher(FileSystemEventHandler):
    """File system watcher for configuration changes"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.debounce_time = 1.0  # 1 second debounce
        self.last_modified = {}
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        path = event.src_path
        current_time = time.time()
        
        # Debounce rapid file changes
        if path in self.last_modified:
            if current_time - self.last_modified[path] < self.debounce_time:
                return
                
        self.last_modified[path] = current_time
        
        # Trigger hot reload for config files
        if path.endswith(('.json', '.yaml', '.yml', '.toml')):
            # Schedule coroutine in a thread-safe way
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(self.config_manager.reload_config_file(path))
                )
            except RuntimeError:
                # No running loop, schedule for later
                threading.Thread(
                    target=self._schedule_reload,
                    args=(path,),
                    daemon=True
                ).start()
    
    def _schedule_reload(self, path: str):
        """Schedule reload in a new thread if no event loop is available"""
        try:
            logger.info(f"Scheduling config reload for {path}")
        except Exception as e:
            logger.error(f"Error scheduling config reload for {path}: {str(e)}")


class ConfigManager:
    """Core configuration management system"""
    
    def __init__(self):
        self.configs: Dict[str, Dict[str, Any]] = {}
        self.schemas: Dict[str, ConfigSchema] = {}
        self.versions: Dict[str, List[ConfigVersion]] = {}
        self.watchers: Dict[str, Observer] = {}
        self.encrypted_configs: set = set()
        self.config_paths: Dict[str, Path] = {}
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.start_time = time.time()
        self.stats = ConfigStats(
            total_configs=0,
            active_watchers=0,
            config_versions=0,
            encrypted_configs=0,
            hot_reloads_performed=0,
            validation_errors=0,
            last_reload_time=datetime.now(),
            uptime=0
        )
        
        # Initialize encryption key
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
        # Base configuration directories
        self.config_base_dir = Path("configs")
        self.config_base_dir.mkdir(exist_ok=True)
        
        # Environment-specific directory
        self.env_config_dir = self.config_base_dir / self.environment
        self.env_config_dir.mkdir(exist_ok=True)
        
        logger.info(f"ConfigManager initialized for environment: {self.environment}")
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for sensitive configurations"""
        key_file = Path(".config_encryption_key")
        
        if key_file.exists():
            return key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            key_file.chmod(0o600)  # Restrict permissions
            logger.info("Generated new encryption key for configuration management")
            return key
    
    def register_schema(self, name: str, schema: ConfigSchema):
        """Register a configuration schema for validation"""
        self.schemas[name] = schema
        logger.info(f"Registered configuration schema: {name}")
    
    def validate_config(self, name: str, config_data: Dict[str, Any]) -> bool:
        """Validate configuration against registered schema"""
        if name not in self.schemas:
            logger.debug(f"No schema registered for config: {name}")
            return True
            
        schema = self.schemas[name]
        
        try:
            # Check required fields
            for field in schema.required_fields:
                if field not in config_data:
                    logger.error(f"Missing required field '{field}' in config '{name}'")
                    self.stats.validation_errors += 1
                    return False
            
            # Validate field types
            for field, expected_type in schema.field_types.items():
                if field in config_data:
                    if not isinstance(config_data[field], expected_type):
                        logger.error(f"Invalid type for field '{field}' in config '{name}'. Expected {expected_type.__name__}")
                        self.stats.validation_errors += 1
                        return False
            
            # Run custom validators
            for field, validator in schema.validators.items():
                if field in config_data:
                    if not validator(config_data[field]):
                        logger.error(f"Validation failed for field '{field}' in config '{name}'")
                        self.stats.validation_errors += 1
                        return False
            
            logger.debug(f"Configuration '{name}' passed validation")
            return True
            
        except Exception as e:
            logger.error(f"Error validating config '{name}': {str(e)}")
            self.stats.validation_errors += 1
            return False
    
    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate checksum for configuration data"""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def _create_version(self, name: str, config_data: Dict[str, Any], description: str = "Auto-save") -> ConfigVersion:
        """Create a new configuration version"""
        version_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        checksum = self._calculate_checksum(config_data)
        
        version = ConfigVersion(
            version=version_id,
            timestamp=datetime.now(),
            checksum=checksum,
            author=os.getenv('USER', 'system'),
            description=description,
            config_data=config_data.copy()
        )
        
        if name not in self.versions:
            self.versions[name] = []
        
        self.versions[name].append(version)
        
        # Keep only last 10 versions
        if len(self.versions[name]) > 10:
            self.versions[name] = self.versions[name][-10:]
        
        self.stats.config_versions += 1
        logger.debug(f"Created version {version_id} for config '{name}'")
        return version
    
    async def set_config(self, name: str, config_data: Dict[str, Any], 
                        encrypted: bool = False, description: str = "Manual update") -> bool:
        """Set configuration with validation and versioning"""
        try:
            # Validate configuration
            if not self.validate_config(name, config_data):
                return False
            
            # Create version before updating
            self._create_version(name, config_data, description)
            
            # Handle encryption if requested
            if encrypted:
                self.encrypted_configs.add(name)
                
            # Store configuration
            self.configs[name] = config_data.copy()
            self.stats.total_configs = len(self.configs)
            
            # Save to file
            await self._save_config_to_file(name, config_data, encrypted)
            
            logger.info(f"Configuration '{name}' updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting config '{name}': {str(e)}")
            return False
    
    async def get_config(self, name: str, default: Any = None) -> Any:
        """Get configuration value"""
        if name in self.configs:
            return self.configs[name]
        
        # Try to load from file if not in memory
        config_data = await self._load_config_from_file(name)
        if config_data is not None:
            self.configs[name] = config_data
            return config_data
            
        return default
    
    async def get_config_value(self, config_name: str, key: str, default: Any = None) -> Any:
        """Get specific value from configuration"""
        config = await self.get_config(config_name)
        if config is None:
            return default
            
        keys = key.split('.')
        value = config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    async def _save_config_to_file(self, name: str, config_data: Dict[str, Any], encrypted: bool = False):
        """Save configuration to file"""
        file_path = self.env_config_dir / f"{name}.json"
        
        try:
            if encrypted:
                # Encrypt sensitive data
                json_str = json.dumps(config_data, indent=2)
                encrypted_data = self.cipher.encrypt(json_str.encode())
                file_path.write_bytes(encrypted_data)
                logger.debug(f"Saved encrypted config '{name}' to {file_path}")
            else:
                # Save as regular JSON
                with open(file_path, 'w') as f:
                    json.dump(config_data, f, indent=2)
                logger.debug(f"Saved config '{name}' to {file_path}")
            
            self.config_paths[name] = file_path
            
        except Exception as e:
            logger.error(f"Error saving config '{name}' to file: {str(e)}")
            raise
    
    async def _load_config_from_file(self, name: str) -> Optional[Dict[str, Any]]:
        """Load configuration from file"""
        file_path = self.env_config_dir / f"{name}.json"
        
        if not file_path.exists():
            return None
        
        try:
            if name in self.encrypted_configs:
                # Decrypt sensitive data
                encrypted_data = file_path.read_bytes()
                decrypted_data = self.cipher.decrypt(encrypted_data)
                return json.loads(decrypted_data.decode())
            else:
                # Load regular JSON
                with open(file_path, 'r') as f:
                    return json.load(f)
                    
        except Exception as e:
            logger.error(f"Error loading config '{name}' from file: {str(e)}")
            return None
    
    async def reload_config_file(self, file_path: str):
        """Hot reload configuration from file change"""
        try:
            path = Path(file_path)
            config_name = path.stem
            
            # Load updated configuration
            if path.suffix == '.json':
                with open(path, 'r') as f:
                    new_config = json.load(f)
            elif path.suffix in ['.yaml', '.yml']:
                with open(path, 'r') as f:
                    new_config = yaml.safe_load(f)
            else:
                logger.warning(f"Unsupported config file format: {path.suffix}")
                return
            
            # Validate and update
            if self.validate_config(config_name, new_config):
                self.configs[config_name] = new_config
                self.stats.hot_reloads_performed += 1
                self.stats.last_reload_time = datetime.now()
                logger.info(f"Hot reloaded configuration '{config_name}' from {file_path}")
            else:
                logger.error(f"Failed to hot reload '{config_name}' - validation failed")
                
        except Exception as e:
            logger.error(f"Error hot reloading config from {file_path}: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get configuration management statistics"""
        self.stats.uptime = time.time() - self.start_time
        return asdict(self.stats)
    
    async def cleanup(self):
        """Cleanup resources"""
        for watcher in self.watchers.values():
            watcher.stop()
            watcher.join()
        
        self.watchers.clear()
        logger.info("Configuration management cleanup completed")


# Global config manager
config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global config manager instance"""
    global config_manager
    if config_manager is None:
        config_manager = ConfigManager()
    return config_manager


async def init_config_manager():
    """Initialize the global config manager"""
    global config_manager
    config_manager = ConfigManager()
    
    # Register default schemas
    await _register_default_schemas()
    
    # Load default configurations
    await _load_default_configs()
    
    logger.info("Configuration manager initialized")


async def _register_default_schemas():
    """Register default configuration schemas"""
    manager = get_config_manager()
    
    # Database schema
    db_schema = ConfigSchema(
        name="database",
        required_fields=["host", "port", "name"],
        optional_fields=["username", "password", "ssl"],
        field_types={"host": str, "port": int, "name": str, "ssl": bool},
        validators={"port": lambda x: 1 <= x <= 65535}
    )
    manager.register_schema("database", db_schema)
    
    # Cache schema
    cache_schema = ConfigSchema(
        name="cache",
        required_fields=["redis_url"],
        optional_fields=["timeout", "max_connections"],
        field_types={"redis_url": str, "timeout": int, "max_connections": int},
        validators={"timeout": lambda x: x > 0}
    )
    manager.register_schema("cache", cache_schema)


async def _load_default_configs():
    """Load default configurations"""
    manager = get_config_manager()
    
    default_configs = {
        "app": {
            "name": "Confidential Empire",
            "version": "1.0.0",
            "debug": manager.environment == "development",
            "log_level": "INFO",
            "timezone": "UTC"
        },
        "cache": {
            "redis_url": "redis://empire-redis:6379/0",
            "timeout": 30,
            "max_connections": 10
        }
    }
    
    for name, config in default_configs.items():
        await manager.set_config(name, config, description="Default configuration")