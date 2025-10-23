"""
API Key Authentication Service
Handles API key validation and user authentication with Redis caching for performance
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import HTTPException, Request, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import verify_api_key
from app.db.database import get_db
from app.models.api_key import APIKey
from app.models.user import User
from app.utils.exceptions import AuthenticationError, AuthorizationError
from app.services.cached_api_key import cached_api_key_service

logger = logging.getLogger(__name__)


class APIKeyAuthService:
    """Service for API key authentication and validation"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def validate_api_key(self, api_key: str, request: Request) -> Optional[Dict[str, Any]]:
        """Validate API key and return user context using Redis cache for performance"""
        try:
            if not api_key:
                return None
            
            # Extract key prefix for lookup
            if len(api_key) < 8:
                logger.warning(f"Invalid API key format: too short")
                return None
            
            key_prefix = api_key[:8]
            
            # Try cached verification first
            cached_verification = await cached_api_key_service.verify_api_key_cached(api_key, key_prefix)
            
            # Get API key data from cache or database
            context = await cached_api_key_service.get_cached_api_key(key_prefix, self.db)
            
            if not context:
                logger.warning(f"API key not found: {key_prefix}")
                return None
            
            api_key_obj = context["api_key"]
            
            # If not in verification cache, verify and cache the result
            if not cached_verification:
                # Get the actual key hash for verification (this should be in the cached context)
                db_api_key = None
                if not hasattr(api_key_obj, 'key_hash'):
                    # Fallback: fetch full API key from database for hash
                    stmt = select(APIKey).where(APIKey.key_prefix == key_prefix)
                    result = await self.db.execute(stmt)
                    db_api_key = result.scalar_one_or_none()
                    if not db_api_key:
                        return None
                    key_hash = db_api_key.key_hash
                else:
                    key_hash = api_key_obj.key_hash
                
                # Verify the API key hash
                if not verify_api_key(api_key, key_hash):
                    logger.warning(f"Invalid API key hash: {key_prefix}")
                    return None
                
                # Cache successful verification
                await cached_api_key_service.cache_verification_result(api_key, key_prefix, key_hash, True)
            
            # Check if key is valid (expiry, active status)
            if not api_key_obj.is_valid():
                logger.warning(f"API key expired or inactive: {key_prefix}")
                # Invalidate cache for expired keys
                await cached_api_key_service.invalidate_api_key_cache(key_prefix)
                return None
            
            # Check IP restrictions
            client_ip = request.client.host if request.client else "unknown"
            if not api_key_obj.can_access_from_ip(client_ip):
                logger.warning(f"IP not allowed for API key {key_prefix}: {client_ip}")
                return None
            
            # Update last used timestamp asynchronously (performance optimization)
            await cached_api_key_service.update_last_used(context["api_key_id"], self.db)
            
            return context
            
        except Exception as e:
            logger.error(f"API key validation error: {e}")
            return None
    
    async def check_endpoint_permission(self, context: Dict[str, Any], endpoint: str) -> bool:
        """Check if API key has permission to access endpoint"""
        api_key: APIKey = context.get("api_key")
        if not api_key:
            return False
        
        return api_key.can_access_endpoint(endpoint)
    
    async def check_model_permission(self, context: Dict[str, Any], model: str) -> bool:
        """Check if API key has permission to access model"""
        api_key: APIKey = context.get("api_key")
        if not api_key:
            return False
        
        return api_key.can_access_model(model)
    
    async def check_scope_permission(self, context: Dict[str, Any], scope: str) -> bool:
        """Check if API key has required scope"""
        api_key: APIKey = context.get("api_key")
        if not api_key:
            return False
        
        return api_key.has_scope(scope)
    
    async def update_usage_stats(self, context: Dict[str, Any], tokens_used: int = 0, cost_cents: int = 0):
        """Update API key usage statistics"""
        try:
            api_key: APIKey = context.get("api_key")
            if api_key:
                api_key.update_usage(tokens_used, cost_cents)
                await self.db.commit()
                logger.info(f"Updated usage for API key {api_key.key_prefix}: +{tokens_used} tokens, +{cost_cents} cents")
        except Exception as e:
            logger.error(f"Failed to update usage stats: {e}")


async def get_api_key_context(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[Dict[str, Any]]:
    """Dependency to get API key context from request"""
    auth_service = APIKeyAuthService(db)

    # Try different auth methods
    api_key = None

    # 1. Check Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        api_key = auth_header[7:]

    # 2. Check X-API-Key header
    if not api_key:
        api_key = request.headers.get("X-API-Key")

    # 3. Check query parameter
    if not api_key:
        api_key = request.query_params.get("api_key")

    if not api_key:
        return None

    return await auth_service.validate_api_key(api_key, request)


async def require_api_key(
    context: Dict[str, Any] = Depends(get_api_key_context)
) -> Dict[str, Any]:
    """Dependency that requires valid API key"""
    if not context:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid API key required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return context


async def get_current_api_key_user(
    context: Dict[str, Any] = Depends(require_api_key)
) -> tuple:
    """
    Dependency that returns current user and API key as a tuple
    
    Returns:
        tuple: (user, api_key)
    """
    user = context.get("user")
    api_key = context.get("api_key")
    
    if not user or not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User or API key not found in context"
        )
    
    return user, api_key


async def get_api_key_auth(
    context: Dict[str, Any] = Depends(require_api_key)
) -> APIKey:
    """
    Dependency that returns the authenticated API key object
    
    Returns:
        APIKey: The authenticated API key object
    """
    api_key = context.get("api_key")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key not found in context"
        )
    
    return api_key


class RequireScope:
    """Dependency class for scope checking"""
    
    def __init__(self, scope: str):
        self.scope = scope
    
    async def __call__(self, context: Dict[str, Any] = Depends(require_api_key)):
        auth_service = APIKeyAuthService(context.get("db"))
        if not await auth_service.check_scope_permission(context, self.scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{self.scope}' required"
            )
        return context


class RequireModel:
    """Dependency class for model access checking"""
    
    def __init__(self, model: str):
        self.model = model
    
    async def __call__(self, context: Dict[str, Any] = Depends(require_api_key)):
        auth_service = APIKeyAuthService(context.get("db"))
        if not await auth_service.check_model_permission(context, self.model):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Model '{self.model}' not allowed"
            )
        return context