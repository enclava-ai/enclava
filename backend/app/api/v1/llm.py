"""
LLM API endpoints - proxy to LiteLLM service with authentication and budget enforcement
"""

import logging
import time
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.api_key_auth import require_api_key, RequireScope, APIKeyAuthService, get_api_key_context
from app.core.security import get_current_user
from app.models.user import User
from app.core.config import settings
from app.services.litellm_client import litellm_client
from app.services.budget_enforcement import (
    check_budget_for_request, record_request_usage, BudgetEnforcementService,
    atomic_check_and_reserve_budget, atomic_finalize_usage
)
from app.services.cost_calculator import CostCalculator, estimate_request_cost
from app.utils.exceptions import AuthenticationError, AuthorizationError
from app.middleware.analytics import set_analytics_data

logger = logging.getLogger(__name__)

# Models response cache - simple in-memory cache for performance
_models_cache = {
    "data": None,
    "cached_at": 0,
    "cache_ttl": 900  # 15 minutes cache TTL
}

router = APIRouter()


async def get_cached_models() -> List[Dict[str, Any]]:
    """Get models from cache or fetch from LiteLLM if cache is stale"""
    current_time = time.time()
    
    # Check if cache is still valid
    if (_models_cache["data"] is not None and 
        current_time - _models_cache["cached_at"] < _models_cache["cache_ttl"]):
        logger.debug("Returning cached models list")
        return _models_cache["data"]
    
    # Cache miss or stale - fetch from LiteLLM
    try:
        logger.debug("Fetching fresh models list from LiteLLM")
        models = await litellm_client.get_models()
        
        # Update cache
        _models_cache["data"] = models
        _models_cache["cached_at"] = current_time
        
        return models
    except Exception as e:
        logger.error(f"Failed to fetch models from LiteLLM: {e}")
        
        # Return stale cache if available, otherwise empty list
        if _models_cache["data"] is not None:
            logger.warning("Returning stale cached models due to fetch error")
            return _models_cache["data"]
        
        return []


def invalidate_models_cache():
    """Invalidate the models cache (useful for admin operations)"""
    _models_cache["data"] = None
    _models_cache["cached_at"] = 0
    logger.info("Models cache invalidated")


# Request/Response Models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="Model name")
    messages: List[ChatMessage] = Field(..., description="List of messages")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(None, description="Temperature for sampling")
    top_p: Optional[float] = Field(None, description="Top-p sampling parameter")
    frequency_penalty: Optional[float] = Field(None, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(None, description="Presence penalty")
    stop: Optional[List[str]] = Field(None, description="Stop sequences")
    stream: Optional[bool] = Field(False, description="Stream response")


class EmbeddingRequest(BaseModel):
    model: str = Field(..., description="Model name")
    input: str = Field(..., description="Input text to embed")
    encoding_format: Optional[str] = Field("float", description="Encoding format")


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]


# Hybrid authentication function
async def get_auth_context(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get authentication context from either API key or JWT token"""
    # Try API key authentication first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        
        # Check if it's an API key (starts with ce_ prefix)
        if token.startswith(settings.API_KEY_PREFIX):
            try:
                context = await get_api_key_context(request, db)
                if context:
                    return context
            except Exception as e:
                logger.warning(f"API key authentication failed: {e}")
        else:
            # Try JWT token authentication
            try:
                from app.core.security import get_current_user
                # Create a fake credentials object for JWT validation
                from fastapi.security import HTTPAuthorizationCredentials
                credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
                user = await get_current_user(credentials, db)
                if user:
                    return {
                        "user": user,
                        "auth_type": "jwt",
                        "api_key": None
                    }
            except Exception as e:
                logger.warning(f"JWT authentication failed: {e}")
    
    # Try X-API-Key header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        try:
            context = await get_api_key_context(request, db)
            if context:
                return context
        except Exception as e:
            logger.warning(f"X-API-Key authentication failed: {e}")
    
    # No valid authentication found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid API key or authentication token required"
    )

# Endpoints
@router.get("/models", response_model=ModelsResponse)
async def list_models(
    context: Dict[str, Any] = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db)
):
    """List available models"""
    try:
        # For JWT users, allow access to list models
        if context.get("auth_type") == "jwt":
            pass  # JWT users can list models
        else:
            # For API key users, check permissions
            auth_service = APIKeyAuthService(db)
            if not await auth_service.check_scope_permission(context, "models.list"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to list models"
                )
        
        # Get models from cache or LiteLLM
        models = await get_cached_models()
        
        # Filter models based on API key permissions
        api_key = context.get("api_key")
        if api_key and api_key.allowed_models:
            models = [model for model in models if model.get("id") in api_key.allowed_models]
        
        return ModelsResponse(data=models)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list models"
        )


@router.post("/models/invalidate-cache")
async def invalidate_models_cache_endpoint(
    context: Dict[str, Any] = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db)
):
    """Invalidate models cache (admin only)"""
    # Check for admin permissions
    if context.get("auth_type") == "jwt":
        user = context.get("user")
        if not user or not user.get("is_superuser"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
    else:
        # For API key users, check admin permissions
        auth_service = APIKeyAuthService(db)
        if not await auth_service.check_scope_permission(context, "admin.cache"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin permissions required to invalidate cache"
            )
    
    invalidate_models_cache()
    return {"message": "Models cache invalidated successfully"}


@router.post("/chat/completions")
async def create_chat_completion(
    request_body: Request,
    chat_request: ChatCompletionRequest,
    context: Dict[str, Any] = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db)
):
    """Create chat completion with budget enforcement"""
    try:
        auth_type = context.get("auth_type", "api_key")
        
        # Handle different authentication types
        if auth_type == "api_key":
            auth_service = APIKeyAuthService(db)
            
            # Check permissions
            if not await auth_service.check_scope_permission(context, "chat.completions"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions for chat completions"
                )
            
            if not await auth_service.check_model_permission(context, chat_request.model):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Model '{chat_request.model}' not allowed"
                )
            
            api_key = context.get("api_key")
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API key information not available"
                )
        elif auth_type == "jwt":
            # For JWT authentication, we'll skip the detailed permission checks for now
            # and create a dummy API key context for budget tracking
            user = context.get("user")
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User information not available"
                )
            api_key = None  # JWT users don't have API keys
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication type"
            )
        
        # Estimate token usage for budget checking
        messages_text = " ".join([msg.content for msg in chat_request.messages])
        estimated_tokens = len(messages_text.split()) * 1.3  # Rough token estimation
        if chat_request.max_tokens:
            estimated_tokens += chat_request.max_tokens
        else:
            estimated_tokens += 150  # Default response length estimate
        
        # Get a synchronous session for budget enforcement
        from app.db.database import SessionLocal
        sync_db = SessionLocal()
        
        try:
            # Atomic budget check and reservation (only for API key users)
            warnings = []
            reserved_budget_ids = []
            if auth_type == "api_key" and api_key:
                is_allowed, error_message, budget_warnings, budget_ids = atomic_check_and_reserve_budget(
                    sync_db, api_key, chat_request.model, int(estimated_tokens), "chat/completions"
                )
                
                if not is_allowed:
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail=f"Budget exceeded: {error_message}"
                    )
                warnings = budget_warnings
                reserved_budget_ids = budget_ids
        
            # Convert messages to dict format
            messages = [{"role": msg.role, "content": msg.content} for msg in chat_request.messages]
            
            # Prepare additional parameters
            kwargs = {}
            if chat_request.max_tokens is not None:
                kwargs["max_tokens"] = chat_request.max_tokens
            if chat_request.temperature is not None:
                kwargs["temperature"] = chat_request.temperature
            if chat_request.top_p is not None:
                kwargs["top_p"] = chat_request.top_p
            if chat_request.frequency_penalty is not None:
                kwargs["frequency_penalty"] = chat_request.frequency_penalty
            if chat_request.presence_penalty is not None:
                kwargs["presence_penalty"] = chat_request.presence_penalty
            if chat_request.stop is not None:
                kwargs["stop"] = chat_request.stop
            if chat_request.stream is not None:
                kwargs["stream"] = chat_request.stream
            
            # Make request to LiteLLM
            response = await litellm_client.create_chat_completion(
                model=chat_request.model,
                messages=messages,
                user_id=str(context.get("user_id", "anonymous")),
                api_key_id=context.get("api_key_id", "jwt_user"),
                **kwargs
            )
            
            # Calculate actual cost and update usage
            usage = response.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
            
            # Calculate accurate cost
            actual_cost_cents = CostCalculator.calculate_cost_cents(
                chat_request.model, input_tokens, output_tokens
            )
            
            # Finalize actual usage in budgets (only for API key users)
            if auth_type == "api_key" and api_key:
                atomic_finalize_usage(
                    sync_db, reserved_budget_ids, api_key, chat_request.model, 
                    input_tokens, output_tokens, "chat/completions"
                )
                
                # Update API key usage statistics
                auth_service = APIKeyAuthService(db)
                await auth_service.update_usage_stats(context, total_tokens, actual_cost_cents)
            
            # Set analytics data for middleware
            set_analytics_data(
                model=chat_request.model,
                request_tokens=input_tokens,
                response_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_cents=actual_cost_cents,
                budget_ids=reserved_budget_ids,
                budget_warnings=warnings
            )
            
            # Add budget warnings to response if any
            if warnings:
                response["budget_warnings"] = warnings
            
            return response
            
        finally:
            sync_db.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating chat completion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chat completion"
        )


@router.post("/embeddings")
async def create_embedding(
    request: EmbeddingRequest,
    context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Create embedding with budget enforcement"""
    try:
        auth_service = APIKeyAuthService(db)
        
        # Check permissions
        if not await auth_service.check_scope_permission(context, "embeddings.create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for embeddings"
            )
        
        if not await auth_service.check_model_permission(context, request.model):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Model '{request.model}' not allowed"
            )
        
        api_key = context.get("api_key")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key information not available"
            )
        
        # Estimate token usage for budget checking
        estimated_tokens = len(request.input.split()) * 1.3  # Rough token estimation
        
        # Convert AsyncSession to Session for budget enforcement
        sync_db = Session(bind=db.bind.sync_engine)
        
        try:
            # Check budget compliance before making request
            is_allowed, error_message, warnings = check_budget_for_request(
                sync_db, api_key, request.model, int(estimated_tokens), "embeddings"
            )
            
            if not is_allowed:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"Budget exceeded: {error_message}"
                )
        
            # Make request to LiteLLM
            response = await litellm_client.create_embedding(
                model=request.model,
                input_text=request.input,
                user_id=str(context["user_id"]),
                api_key_id=context["api_key_id"],
                encoding_format=request.encoding_format
            )
            
            # Calculate actual cost and update usage
            usage = response.get("usage", {})
            total_tokens = usage.get("total_tokens", int(estimated_tokens))
            
            # Calculate accurate cost (embeddings typically use input tokens only)
            actual_cost_cents = CostCalculator.calculate_cost_cents(
                request.model, total_tokens, 0
            )
            
            # Record actual usage in budgets
            record_request_usage(
                sync_db, api_key, request.model, total_tokens, 0, "embeddings"
            )
            
            # Update API key usage statistics
            await auth_service.update_usage_stats(context, total_tokens, actual_cost_cents)
            
            # Add budget warnings to response if any
            if warnings:
                response["budget_warnings"] = warnings
            
            return response
            
        finally:
            sync_db.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating embedding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create embedding"
        )


@router.get("/health")
async def llm_health_check(
    context: Dict[str, Any] = Depends(require_api_key)
):
    """Health check for LLM service"""
    try:
        health_status = await litellm_client.health_check()
        return {
            "status": "healthy",
            "service": "LLM Proxy",
            "litellm_status": health_status,
            "user_id": context["user_id"],
            "api_key_name": context["api_key_name"]
        }
    except Exception as e:
        logger.error(f"LLM health check error: {e}")
        return {
            "status": "unhealthy",
            "service": "LLM Proxy",
            "error": str(e)
        }


@router.get("/usage")
async def get_usage_stats(
    context: Dict[str, Any] = Depends(require_api_key)
):
    """Get usage statistics for the API key"""
    try:
        api_key = context.get("api_key")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key information not available"
            )
        
        return {
            "api_key_id": api_key.id,
            "api_key_name": api_key.name,
            "total_requests": api_key.total_requests,
            "total_tokens": api_key.total_tokens,
            "total_cost_cents": api_key.total_cost,
            "created_at": api_key.created_at.isoformat(),
            "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
            "rate_limits": {
                "per_minute": api_key.rate_limit_per_minute,
                "per_hour": api_key.rate_limit_per_hour,
                "per_day": api_key.rate_limit_per_day
            },
            "permissions": api_key.permissions,
            "scopes": api_key.scopes,
            "allowed_models": api_key.allowed_models
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting usage stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get usage statistics"
        )


@router.get("/budget/status")
async def get_budget_status(
    request: Request,
    context: Dict[str, Any] = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db)
):
    """Get current budget status and usage analytics"""
    try:
        auth_type = context.get("auth_type", "api_key")
        
        # Check permissions based on auth type
        if auth_type == "api_key":
            auth_service = APIKeyAuthService(db)
            if not await auth_service.check_scope_permission(context, "budget.read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to read budget information"
                )
            
            api_key = context.get("api_key")
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API key information not available"
                )
            
            # Convert AsyncSession to Session for budget enforcement
            sync_db = Session(bind=db.bind.sync_engine)
            
            try:
                budget_service = BudgetEnforcementService(sync_db)
                budget_status = budget_service.get_budget_status(api_key)
                
                return {
                    "object": "budget_status",
                    "data": budget_status
                }
            finally:
                sync_db.close()
                
        elif auth_type == "jwt":
            # For JWT authentication, return user-level budget information
            user = context.get("user")
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User information not available"
                )
            
            # Return basic budget info for JWT users
            return {
                "object": "budget_status",
                "data": {
                    "budgets": [],
                    "total_usage": 0.0,
                    "warnings": [],
                    "projections": {
                        "daily_burn_rate": 0.0,
                        "projected_monthly": 0.0,
                        "days_remaining": 30
                    }
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication type"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting budget status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get budget status"
        )


# Generic proxy endpoint for other LiteLLM endpoints
@router.api_route("/{endpoint:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_endpoint(
    endpoint: str,
    request: Request,
    context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Generic proxy endpoint for LiteLLM requests"""
    try:
        auth_service = APIKeyAuthService(db)
        
        # Check endpoint permission
        if not await auth_service.check_endpoint_permission(context, endpoint):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Endpoint '{endpoint}' not allowed"
            )
        
        # Get request body
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                payload = await request.json()
            except:
                payload = {}
        else:
            payload = dict(request.query_params)
        
        # Make request to LiteLLM
        response = await litellm_client.proxy_request(
            method=request.method,
            endpoint=endpoint,
            payload=payload,
            user_id=str(context["user_id"]),
            api_key_id=context["api_key_id"]
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxying request to {endpoint}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to proxy request"
        )