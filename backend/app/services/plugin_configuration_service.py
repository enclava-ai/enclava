"""
Plugin Configuration Service
Handles persistent storage and caching of plugin configurations
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import selectinload
import json
import redis
import logging

from app.models.plugin import Plugin, PluginConfiguration
from app.models.user import User
from app.core.config import settings
from app.utils.exceptions import APIException

logger = logging.getLogger(__name__)


class PluginConfigurationService:
    """Service for managing plugin configurations with persistent storage and caching"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
        # Initialize Redis for caching (optional, will gracefully degrade)
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            self._redis_available = True
            logger.info("Redis available for plugin configuration caching")
        except Exception as e:
            logger.warning(f"Redis not available for plugin configuration caching: {e}")
            self.redis_client = None
            self._redis_available = False
        
        # In-memory cache as fallback
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
    
    def _get_cache_key(self, plugin_id: str, user_id: str, config_key: str = "") -> str:
        """Generate cache key for configuration"""
        if config_key:
            return f"plugin_config:{plugin_id}:{user_id}:{config_key}"
        else:
            return f"plugin_config:{plugin_id}:{user_id}:*"
    
    async def get_configuration(
        self, 
        plugin_id: str, 
        user_id: str, 
        config_key: str,
        default_value: Any = None
    ) -> Any:
        """Get a specific configuration value"""
        
        # Try cache first
        cache_key = self._get_cache_key(plugin_id, user_id, config_key)
        
        if self._redis_available:
            try:
                cached_value = self.redis_client.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return json.loads(cached_value)
            except Exception as e:
                logger.warning(f"Redis cache read failed: {e}")
        
        # Check memory cache
        mem_cache_key = f"{plugin_id}:{user_id}:{config_key}"
        if mem_cache_key in self._memory_cache:
            logger.debug(f"Memory cache hit for {mem_cache_key}")
            return self._memory_cache[mem_cache_key]
        
        # Load from database
        try:
            stmt = select(PluginConfiguration).where(
                and_(
                    PluginConfiguration.plugin_id == plugin_id,
                    PluginConfiguration.user_id == user_id,
                    PluginConfiguration.is_active == True
                )
            )
            result = await self.db.execute(stmt)
            config = result.scalar_one_or_none()
            
            if config and config.config_data:
                config_value = config.config_data.get(config_key, default_value)
                
                # Cache the value
                await self._cache_value(cache_key, mem_cache_key, config_value)
                
                logger.debug(f"Database hit for {cache_key}")
                return config_value
            
            logger.debug(f"Configuration not found for {cache_key}, returning default")
            return default_value
            
        except Exception as e:
            logger.error(f"Failed to get configuration {config_key} for plugin {plugin_id}: {e}")
            return default_value
    
    async def set_configuration(
        self, 
        plugin_id: str, 
        user_id: str, 
        config_key: str, 
        config_value: Any,
        config_type: str = "user_setting"
    ) -> bool:
        """Set a configuration value with write-through caching"""
        
        try:
            # Get or create plugin configuration record
            stmt = select(PluginConfiguration).where(
                and_(
                    PluginConfiguration.plugin_id == plugin_id,
                    PluginConfiguration.user_id == user_id,
                    PluginConfiguration.is_active == True
                )
            )
            result = await self.db.execute(stmt)
            config = result.scalar_one_or_none()
            
            if config:
                # Update existing configuration
                if config.config_data is None:
                    config.config_data = {}
                
                config.config_data[config_key] = config_value
                config.updated_at = datetime.utcnow()
                
                # Use update to ensure proper JSON serialization
                stmt = update(PluginConfiguration).where(
                    PluginConfiguration.id == config.id
                ).values(
                    config_data=config.config_data,
                    updated_at=datetime.utcnow()
                )
                await self.db.execute(stmt)
            else:
                # Create new configuration
                config = PluginConfiguration(
                    plugin_id=plugin_id,
                    user_id=user_id,
                    name=f"Config for {plugin_id}",
                    description="Plugin configuration",
                    config_data={config_key: config_value},
                    is_active=True,
                    created_by_user_id=user_id
                )
                self.db.add(config)
            
            await self.db.commit()
            
            # Write-through caching
            cache_key = self._get_cache_key(plugin_id, user_id, config_key)
            mem_cache_key = f"{plugin_id}:{user_id}:{config_key}"
            await self._cache_value(cache_key, mem_cache_key, config_value)
            
            logger.info(f"Set configuration {config_key} for plugin {plugin_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to set configuration {config_key} for plugin {plugin_id}: {e}")
            return False
    
    async def get_all_configurations(
        self, 
        plugin_id: str, 
        user_id: str
    ) -> Dict[str, Any]:
        """Get all configuration values for a plugin/user combination"""
        
        try:
            stmt = select(PluginConfiguration).where(
                and_(
                    PluginConfiguration.plugin_id == plugin_id,
                    PluginConfiguration.user_id == user_id,
                    PluginConfiguration.is_active == True
                )
            )
            result = await self.db.execute(stmt)
            config = result.scalar_one_or_none()
            
            if config and config.config_data:
                return config.config_data
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Failed to get all configurations for plugin {plugin_id}: {e}")
            return {}
    
    async def set_multiple_configurations(
        self, 
        plugin_id: str, 
        user_id: str, 
        config_data: Dict[str, Any]
    ) -> bool:
        """Set multiple configuration values at once"""
        
        try:
            # Get or create plugin configuration record
            stmt = select(PluginConfiguration).where(
                and_(
                    PluginConfiguration.plugin_id == plugin_id,
                    PluginConfiguration.user_id == user_id,
                    PluginConfiguration.is_active == True
                )
            )
            result = await self.db.execute(stmt)
            config = result.scalar_one_or_none()
            
            if config:
                # Update existing configuration
                if config.config_data is None:
                    config.config_data = {}
                
                config.config_data.update(config_data)
                config.updated_at = datetime.utcnow()
                
                stmt = update(PluginConfiguration).where(
                    PluginConfiguration.id == config.id
                ).values(
                    config_data=config.config_data,
                    updated_at=datetime.utcnow()
                )
                await self.db.execute(stmt)
            else:
                # Create new configuration
                config = PluginConfiguration(
                    plugin_id=plugin_id,
                    user_id=user_id,
                    name=f"Config for {plugin_id}",
                    description="Plugin configuration",
                    config_data=config_data,
                    is_active=True,
                    created_by_user_id=user_id
                )
                self.db.add(config)
            
            await self.db.commit()
            
            # Update cache for all keys
            for config_key, config_value in config_data.items():
                cache_key = self._get_cache_key(plugin_id, user_id, config_key)
                mem_cache_key = f"{plugin_id}:{user_id}:{config_key}"
                await self._cache_value(cache_key, mem_cache_key, config_value)
            
            logger.info(f"Set {len(config_data)} configurations for plugin {plugin_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to set multiple configurations for plugin {plugin_id}: {e}")
            return False
    
    async def delete_configuration(
        self, 
        plugin_id: str, 
        user_id: str, 
        config_key: str
    ) -> bool:
        """Delete a specific configuration key"""
        
        try:
            # Get plugin configuration record
            stmt = select(PluginConfiguration).where(
                and_(
                    PluginConfiguration.plugin_id == plugin_id,
                    PluginConfiguration.user_id == user_id,
                    PluginConfiguration.is_active == True
                )
            )
            result = await self.db.execute(stmt)
            config = result.scalar_one_or_none()
            
            if config and config.config_data and config_key in config.config_data:
                # Remove the key from config_data
                del config.config_data[config_key]
                config.updated_at = datetime.utcnow()
                
                stmt = update(PluginConfiguration).where(
                    PluginConfiguration.id == config.id
                ).values(
                    config_data=config.config_data,
                    updated_at=datetime.utcnow()
                )
                await self.db.execute(stmt)
                await self.db.commit()
                
                # Remove from cache
                cache_key = self._get_cache_key(plugin_id, user_id, config_key)
                mem_cache_key = f"{plugin_id}:{user_id}:{config_key}"
                await self._remove_from_cache(cache_key, mem_cache_key)
                
                logger.info(f"Deleted configuration {config_key} for plugin {plugin_id}")
                return True
            
            return False
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete configuration {config_key} for plugin {plugin_id}: {e}")
            return False
    
    async def clear_plugin_configurations(self, plugin_id: str, user_id: str) -> bool:
        """Clear all configurations for a plugin/user combination"""
        
        try:
            stmt = delete(PluginConfiguration).where(
                and_(
                    PluginConfiguration.plugin_id == plugin_id,
                    PluginConfiguration.user_id == user_id
                )
            )
            await self.db.execute(stmt)
            await self.db.commit()
            
            # Clear from cache
            await self._clear_plugin_cache(plugin_id, user_id)
            
            logger.info(f"Cleared all configurations for plugin {plugin_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to clear configurations for plugin {plugin_id}: {e}")
            return False
    
    async def _cache_value(self, cache_key: str, mem_cache_key: str, value: Any):
        """Store value in both Redis and memory cache"""
        
        # Store in Redis
        if self._redis_available:
            try:
                self.redis_client.setex(
                    cache_key, 
                    3600,  # 1 hour TTL
                    json.dumps(value)
                )
            except Exception as e:
                logger.warning(f"Redis cache write failed: {e}")
        
        # Store in memory cache
        self._memory_cache[mem_cache_key] = value
    
    async def _remove_from_cache(self, cache_key: str, mem_cache_key: str):
        """Remove value from both Redis and memory cache"""
        
        # Remove from Redis
        if self._redis_available:
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Redis cache delete failed: {e}")
        
        # Remove from memory cache
        if mem_cache_key in self._memory_cache:
            del self._memory_cache[mem_cache_key]
    
    async def _clear_plugin_cache(self, plugin_id: str, user_id: str):
        """Clear all cached values for a plugin/user combination"""
        
        # Clear from Redis
        if self._redis_available:
            try:
                pattern = self._get_cache_key(plugin_id, user_id, "*")
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis cache clear failed: {e}")
        
        # Clear from memory cache
        prefix = f"{plugin_id}:{user_id}:"
        keys_to_remove = [k for k in self._memory_cache.keys() if k.startswith(prefix)]
        for key in keys_to_remove:
            del self._memory_cache[key]
    
    async def get_configuration_stats(self) -> Dict[str, Any]:
        """Get statistics about plugin configurations"""
        
        try:
            from sqlalchemy import func
            
            # Count total configurations
            total_stmt = select(func.count(PluginConfiguration.id))
            total_result = await self.db.execute(total_stmt)
            total_configs = total_result.scalar() or 0
            
            # Count active configurations
            active_stmt = select(func.count(PluginConfiguration.id)).where(
                PluginConfiguration.is_active == True
            )
            active_result = await self.db.execute(active_stmt)
            active_configs = active_result.scalar() or 0
            
            return {
                "total_configurations": total_configs,
                "active_configurations": active_configs,
                "cache_size": len(self._memory_cache),
                "redis_available": self._redis_available,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get configuration stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }