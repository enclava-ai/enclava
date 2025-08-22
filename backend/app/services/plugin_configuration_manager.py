"""
Plugin Configuration Manager
Elegant, secure, and developer-friendly plugin configuration system

Design Principles:
1. Schemas embedded in plugin manifests (no hardcoding)
2. Automatic encryption for sensitive fields 
3. Intelligent field type handling
4. Configuration resolution chain (defaults → user overrides)
5. Schema validation and caching
6. UUID-based operations throughout
"""

import json
import uuid
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timezone
from pathlib import Path
from cryptography.fernet import Fernet
from pydantic import BaseModel, ValidationError
import jsonschema
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger
from app.models.plugin import Plugin, PluginConfiguration
from app.utils.exceptions import PluginError

logger = get_logger("plugin.config.manager")

class ConfigurationField(BaseModel):
    """Represents a configuration field with type intelligence"""
    name: str
    value: Any
    field_type: str
    format: Optional[str] = None
    is_sensitive: bool = False
    is_encrypted: bool = False
    validation_rules: Dict[str, Any] = {}

class ConfigurationResolver:
    """Resolves configuration from multiple sources with proper precedence"""
    
    def __init__(self):
        self.logger = get_logger("plugin.config.resolver")
    
    def resolve_configuration(
        self, 
        plugin_manifest: Dict[str, Any],
        user_config: Optional[Dict[str, Any]] = None,
        runtime_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resolve configuration from multiple sources:
        1. Manifest defaults (lowest priority)
        2. User configuration (medium priority) 
        3. Runtime overrides (highest priority)
        """
        # Start with manifest defaults
        schema = plugin_manifest.get("spec", {}).get("config_schema", {})
        resolved = self._extract_defaults_from_schema(schema)
        
        # Apply user configuration
        if user_config:
            resolved.update(user_config)
        
        # Apply runtime overrides
        if runtime_overrides:
            resolved.update(runtime_overrides)
        
        return resolved
    
    def _extract_defaults_from_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract default values from JSON schema"""
        defaults = {}
        properties = schema.get("properties", {})
        
        for field_name, field_schema in properties.items():
            if "default" in field_schema:
                defaults[field_name] = field_schema["default"]
            elif field_schema.get("type") == "object":
                # Recursively extract defaults from nested objects
                nested_defaults = self._extract_defaults_from_schema(field_schema)
                if nested_defaults:
                    defaults[field_name] = nested_defaults
        
        return defaults

class PluginEncryptionManager:
    """Handles encryption/decryption of sensitive configuration fields"""
    
    def __init__(self):
        self.logger = get_logger("plugin.encryption")
        self._encryption_key = self._get_or_generate_key()
        self._cipher = Fernet(self._encryption_key)
    
    def _get_or_generate_key(self) -> bytes:
        """Get existing encryption key or generate new one"""
        # In production, this should be stored securely (e.g., HashiCorp Vault)
        key_env = settings.PLUGIN_ENCRYPTION_KEY if hasattr(settings, 'PLUGIN_ENCRYPTION_KEY') else None
        
        if key_env:
            return key_env.encode()
        
        # Generate new key for development
        key = Fernet.generate_key()
        self.logger.warning(
            "Generated new encryption key for plugin configurations. "
            f"For production, set PLUGIN_ENCRYPTION_KEY environment variable"
        )
        return key
    
    def encrypt_value(self, value: str) -> str:
        """Encrypt a sensitive configuration value"""
        try:
            encrypted = self._cipher.encrypt(value.encode())
            return encrypted.decode()
        except Exception as e:
            self.logger.error(f"Encryption failed: {e}")
            raise PluginError(f"Failed to encrypt configuration value: {e}")
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a sensitive configuration value"""
        try:
            decrypted = self._cipher.decrypt(encrypted_value.encode())
            return decrypted.decode()
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            raise PluginError(f"Failed to decrypt configuration value: {e}")
    
    def identify_sensitive_fields(self, schema: Dict[str, Any]) -> List[str]:
        """Identify sensitive fields in schema that should be encrypted"""
        sensitive_fields = []
        properties = schema.get("properties", {})
        
        for field_name, field_schema in properties.items():
            # Check for explicit sensitive formats
            format_type = field_schema.get("format", "")
            if format_type in ["password", "secret", "token", "key"]:
                sensitive_fields.append(field_name)
            
            # Check for sensitive field names
            if any(keyword in field_name.lower() for keyword in 
                   ["password", "secret", "token", "key", "credential", "private"]):
                sensitive_fields.append(field_name)
            
            # Recursively check nested objects
            if field_schema.get("type") == "object":
                nested_sensitive = self.identify_sensitive_fields(field_schema)
                sensitive_fields.extend([f"{field_name}.{nested}" for nested in nested_sensitive])
        
        return sensitive_fields

class PluginSchemaManager:
    """Manages plugin configuration schemas with caching and validation"""
    
    def __init__(self):
        self.logger = get_logger("plugin.schema.manager")
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self.resolver = ConfigurationResolver()
        self.encryption = PluginEncryptionManager()
    
    async def get_plugin_schema(self, plugin_id: Union[str, uuid.UUID], db: AsyncSession) -> Optional[Dict[str, Any]]:
        """Get configuration schema for plugin (with caching)"""
        plugin_uuid = self._ensure_uuid(plugin_id)
        cache_key = str(plugin_uuid)
        
        # Check cache first
        if cache_key in self._schema_cache:
            cache_time = self._cache_timestamps.get(cache_key)
            if cache_time and (datetime.now() - cache_time).total_seconds() < 300:  # 5 min cache
                return self._schema_cache[cache_key]
        
        # Load from database
        stmt = select(Plugin).where(Plugin.id == plugin_uuid)
        result = await db.execute(stmt)
        plugin = result.scalar_one_or_none()
        
        if not plugin:
            self.logger.warning(f"Plugin not found: {plugin_id}")
            return None
        
        # Extract schema from manifest
        manifest_data = plugin.manifest_data
        if not manifest_data:
            self.logger.warning(f"No manifest data for plugin {plugin.slug}")
            return None
        
        schema = manifest_data.get("spec", {}).get("config_schema")
        if not schema:
            self.logger.warning(f"No config_schema in manifest for plugin {plugin.slug}")
            return None
        
        # Cache the schema
        self._schema_cache[cache_key] = schema
        self._cache_timestamps[cache_key] = datetime.now()
        
        return schema
    
    async def validate_configuration(
        self, 
        plugin_id: Union[str, uuid.UUID], 
        config_data: Dict[str, Any],
        db: AsyncSession
    ) -> Tuple[bool, List[str]]:
        """Validate configuration against plugin schema"""
        schema = await self.get_plugin_schema(plugin_id, db)
        if not schema:
            return False, ["No configuration schema available for plugin"]
        
        try:
            jsonschema.validate(config_data, schema)
            return True, []
        except jsonschema.ValidationError as e:
            return False, [str(e)]
        except Exception as e:
            self.logger.error(f"Schema validation error: {e}")
            return False, [f"Validation failed: {e}"]
    
    async def process_configuration_fields(
        self, 
        plugin_id: Union[str, uuid.UUID],
        config_data: Dict[str, Any],
        db: AsyncSession,
        encrypt_sensitive: bool = True
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Process configuration fields, separating sensitive from non-sensitive data.
        Returns (non_sensitive_data, encrypted_sensitive_data)
        """
        schema = await self.get_plugin_schema(plugin_id, db)
        if not schema:
            return config_data, {}
        
        sensitive_fields = self.encryption.identify_sensitive_fields(schema)
        non_sensitive = {}
        encrypted_sensitive = {}
        
        # Process top-level and nested fields
        for key, value in config_data.items():
            if key in sensitive_fields and encrypt_sensitive:
                # Top-level sensitive field
                encrypted_value = self.encryption.encrypt_value(str(value))
                encrypted_sensitive[key] = encrypted_value
            elif isinstance(value, dict):
                # Process nested object
                nested_sensitive, nested_encrypted = self._process_nested_fields(
                    value, key, sensitive_fields, encrypt_sensitive
                )
                if nested_encrypted:
                    # Store nested encrypted fields with dot notation
                    for nested_key, encrypted_val in nested_encrypted.items():
                        encrypted_sensitive[f"{key}.{nested_key}"] = encrypted_val
                    # Store the non-sensitive parts of the nested object
                    if nested_sensitive:
                        non_sensitive[key] = nested_sensitive
                else:
                    # No sensitive fields in this nested object
                    non_sensitive[key] = value
            else:
                non_sensitive[key] = value
        
        return non_sensitive, encrypted_sensitive
    
    def _process_nested_fields(
        self,
        nested_data: Dict[str, Any],
        parent_key: str,
        sensitive_fields: List[str],
        encrypt_sensitive: bool
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Process nested fields for encryption"""
        nested_non_sensitive = {}
        nested_encrypted = {}
        
        for nested_key, nested_value in nested_data.items():
            full_field_path = f"{parent_key}.{nested_key}"
            if full_field_path in sensitive_fields and encrypt_sensitive:
                # This nested field is sensitive - encrypt it
                encrypted_value = self.encryption.encrypt_value(str(nested_value))
                nested_encrypted[nested_key] = encrypted_value
            else:
                # This nested field is not sensitive
                nested_non_sensitive[nested_key] = nested_value
        
        return nested_non_sensitive, nested_encrypted
    
    def decrypt_configuration(
        self, 
        non_sensitive_data: Dict[str, Any],
        encrypted_sensitive_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine and decrypt configuration for plugin use"""
        decrypted_config = non_sensitive_data.copy()
        
        for key, encrypted_value in encrypted_sensitive_data.items():
            try:
                decrypted_value = self.encryption.decrypt_value(encrypted_value)
                
                if "." in key:
                    # Handle nested fields with dot notation
                    parent_key, nested_key = key.split(".", 1)
                    if parent_key not in decrypted_config:
                        decrypted_config[parent_key] = {}
                    if isinstance(decrypted_config[parent_key], dict):
                        decrypted_config[parent_key][nested_key] = decrypted_value
                    else:
                        self.logger.warning(f"Cannot set nested field {key} - parent is not dict")
                else:
                    # Top-level field
                    decrypted_config[key] = decrypted_value
            except Exception as e:
                self.logger.error(f"Failed to decrypt field {key}: {e}")
                # Continue with other fields, log error
        
        return decrypted_config
    
    def _ensure_uuid(self, plugin_id: Union[str, uuid.UUID]) -> uuid.UUID:
        """Ensure plugin_id is a UUID"""
        if isinstance(plugin_id, uuid.UUID):
            return plugin_id
        
        try:
            return uuid.UUID(plugin_id)
        except ValueError:
            raise PluginError(f"Invalid plugin ID format: {plugin_id}")

class PluginConfigurationManager:
    """Main configuration manager that orchestrates all operations"""
    
    def __init__(self):
        self.logger = get_logger("plugin.config.manager")
        self.schema_manager = PluginSchemaManager()
        self.resolver = ConfigurationResolver()
    
    async def get_plugin_configuration_schema(
        self, 
        plugin_id: Union[str, uuid.UUID], 
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Get configuration schema for plugin"""
        return await self.schema_manager.get_plugin_schema(plugin_id, db)
    
    async def save_plugin_configuration(
        self,
        plugin_id: Union[str, uuid.UUID],
        user_id: int,
        config_data: Dict[str, Any],
        config_name: str = "Default Configuration",
        config_description: Optional[str] = None,
        db: AsyncSession = None
    ) -> PluginConfiguration:
        """Save plugin configuration with automatic encryption of sensitive fields"""
        
        # Check for existing configuration to handle empty sensitive fields
        plugin_uuid = self.schema_manager._ensure_uuid(plugin_id)
        stmt = select(PluginConfiguration).where(
            PluginConfiguration.plugin_id == plugin_uuid,
            PluginConfiguration.user_id == user_id,
            PluginConfiguration.is_active == True
        )
        result = await db.execute(stmt)
        existing_config = result.scalar_one_or_none()
        
        # Handle validation for existing vs new configurations
        validation_passed = False
        
        if existing_config:
            # For existing configurations, use relaxed validation for empty sensitive fields
            try:
                # Try to get existing decrypted configuration
                existing_data = await self.get_plugin_configuration(plugin_id, user_id, db, decrypt_sensitive=True)
                
                if existing_data:
                    # Successfully decrypted - preserve existing sensitive fields
                    schema = await self.schema_manager.get_plugin_schema(plugin_id, db)
                    if schema:
                        sensitive_fields = self.schema_manager.encryption.identify_sensitive_fields(schema)
                        validation_config = config_data.copy()
                        
                        for field in sensitive_fields:
                            if not validation_config.get(field) or str(validation_config.get(field)).strip() == '':
                                if existing_data.get(field):
                                    validation_config[field] = existing_data[field]
                    
                    # Validate with complete config
                    is_valid, errors = await self.schema_manager.validate_configuration(plugin_id, validation_config, db)
                    if is_valid:
                        validation_passed = True
                    else:
                        raise PluginError(f"Configuration validation failed: {', '.join(errors)}")
                
            except Exception as e:
                # Decryption failed - use relaxed validation for updates
                self.logger.warning(f"Using relaxed validation due to decryption error: {e}")
                
                schema = await self.schema_manager.get_plugin_schema(plugin_id, db)
                if schema:
                    # Create relaxed schema that allows empty sensitive fields for existing configs
                    relaxed_schema = schema.copy()
                    sensitive_fields = self.schema_manager.encryption.identify_sensitive_fields(schema)
                    
                    for field in sensitive_fields:
                        if field in relaxed_schema.get("properties", {}):
                            field_props = relaxed_schema["properties"][field]
                            # If field is empty, relax validation requirements
                            if not config_data.get(field) or str(config_data.get(field)).strip() == '':
                                # Remove minLength and other constraints
                                field_props.pop("minLength", None)
                                field_props.pop("pattern", None)
                                # Make it optional
                                if "required" in relaxed_schema and field in relaxed_schema["required"]:
                                    relaxed_schema["required"] = [r for r in relaxed_schema["required"] if r != field]
                    
                    # Validate with relaxed schema
                    try:
                        jsonschema.validate(config_data, relaxed_schema)
                        validation_passed = True
                        validation_config = config_data
                    except jsonschema.ValidationError as ve:
                        raise PluginError(f"Configuration validation failed: {ve}")
        else:
            # New configuration - full validation required
            is_valid, errors = await self.schema_manager.validate_configuration(plugin_id, config_data, db)
            if is_valid:
                validation_passed = True
                validation_config = config_data
            else:
                raise PluginError(f"Configuration validation failed: {', '.join(errors)}")
        
        if not validation_passed:
            raise PluginError("Configuration validation failed")
        
        # Handle encryption for new vs existing configurations
        if existing_config and existing_config.encrypted_data:
            # For existing configs, preserve encrypted data for fields not provided
            try:
                existing_encrypted = json.loads(existing_config.encrypted_data)
            except:
                existing_encrypted = {}
            
            # Identify which sensitive fields are actually being updated
            schema = await self.schema_manager.get_plugin_schema(plugin_id, db)
            sensitive_fields = self.schema_manager.encryption.identify_sensitive_fields(schema) if schema else []
            
            # Process only fields that have new values
            fields_to_encrypt = {}
            for field in sensitive_fields:
                if config_data.get(field) and str(config_data.get(field)).strip():
                    # User provided new value - encrypt it
                    fields_to_encrypt[field] = config_data[field]
            
            # Encrypt new fields
            new_encrypted = {}
            if fields_to_encrypt:
                for field, value in fields_to_encrypt.items():
                    new_encrypted[field] = self.schema_manager.encryption.encrypt_value(str(value))
            
            # Combine existing and new encrypted data
            final_encrypted = {**existing_encrypted, **new_encrypted}
            
            # Process non-sensitive fields
            non_sensitive = {}
            for key, value in config_data.items():
                if key not in sensitive_fields:
                    non_sensitive[key] = value
            
            encrypted_sensitive = final_encrypted
        else:
            # New configuration or no existing encrypted data - process normally
            non_sensitive, encrypted_sensitive = await self.schema_manager.process_configuration_fields(
                plugin_id, validation_config, db, encrypt_sensitive=True
            )
        
        if existing_config:
            # Update existing configuration
            existing_config.config_data = non_sensitive
            existing_config.encrypted_data = json.dumps(encrypted_sensitive) if encrypted_sensitive else None
            existing_config.updated_at = datetime.now()
            existing_config.description = config_description or existing_config.description
        else:
            # Create new configuration
            config = PluginConfiguration(
                id=uuid.uuid4(),
                plugin_id=plugin_uuid,
                user_id=user_id,
                name=config_name,
                description=config_description,
                config_data=non_sensitive,
                encrypted_data=json.dumps(encrypted_sensitive) if encrypted_sensitive else None,
                is_active=True,
                is_default=True,  # First config is default
                created_by_user_id=user_id
            )
            db.add(config)
            existing_config = config
        
        await db.commit()
        return existing_config
    
    async def get_plugin_configuration(
        self,
        plugin_id: Union[str, uuid.UUID],
        user_id: int,
        db: AsyncSession,
        decrypt_sensitive: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get plugin configuration for user with automatic decryption"""
        
        plugin_uuid = self.schema_manager._ensure_uuid(plugin_id)
        stmt = select(PluginConfiguration).where(
            PluginConfiguration.plugin_id == plugin_uuid,
            PluginConfiguration.user_id == user_id,
            PluginConfiguration.is_active == True
        )
        result = await db.execute(stmt)
        config = result.scalar_one_or_none()
        
        if not config:
            return None
        
        # Get non-sensitive data
        config_data = config.config_data or {}
        
        # Decrypt sensitive data if requested
        if decrypt_sensitive and config.encrypted_data:
            try:
                encrypted_data = json.loads(config.encrypted_data)
                decrypted_config = self.schema_manager.decrypt_configuration(config_data, encrypted_data)
                return decrypted_config
            except Exception as e:
                self.logger.error(f"Failed to decrypt configuration: {e}")
                # Return non-sensitive data only
                return config_data
        
        return config_data
    
    async def get_resolved_configuration(
        self,
        plugin_id: Union[str, uuid.UUID],
        user_id: int,
        db: AsyncSession,
        runtime_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get fully resolved configuration (defaults + user config + overrides)"""
        
        # Get plugin manifest for defaults
        plugin_uuid = self.schema_manager._ensure_uuid(plugin_id)
        stmt = select(Plugin).where(Plugin.id == plugin_uuid)
        result = await db.execute(stmt)
        plugin = result.scalar_one_or_none()
        
        if not plugin:
            raise PluginError(f"Plugin not found: {plugin_id}")
        
        # Get user configuration
        user_config = await self.get_plugin_configuration(plugin_id, user_id, db, decrypt_sensitive=True)
        
        # Resolve configuration chain
        resolved = self.resolver.resolve_configuration(
            plugin_manifest=plugin.manifest_data,
            user_config=user_config,
            runtime_overrides=runtime_overrides
        )
        
        return resolved

# Global instance
plugin_config_manager = PluginConfigurationManager()