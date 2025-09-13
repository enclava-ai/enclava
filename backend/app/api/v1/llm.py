"""
LLM API endpoints - interface to secure LLM service with authentication and budget enforcement
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
from app.services.llm.service import llm_service
from app.services.llm.models import ChatRequest, ChatMessage as LLMChatMessage, EmbeddingRequest as LLMEmbeddingRequest
from app.services.llm.exceptions import LLMError, ProviderError, SecurityError, ValidationError
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
    """Get models from cache or fetch from LLM service if cache is stale"""
    current_time = time.time()
    
    # Check if cache is still valid
    if (_models_cache["data"] is not None and 
        current_time - _models_cache["cached_at"] < _models_cache["cache_ttl"]):
        logger.debug("Returning cached models list")
        return _models_cache["data"]
    
    # Cache miss or stale - fetch from LLM service
    try:
        logger.debug("Fetching fresh models list from LLM service")
        model_infos = await llm_service.get_models()
        
        # Convert ModelInfo objects to dict format for compatibility
        models = []
        for model_info in model_infos:
            model_dict = {
                "id": model_info.id,
                "object": model_info.object,
                "created": model_info.created or int(time.time()),
                "owned_by": model_info.owned_by,
                # Add frontend-expected fields
                "name": getattr(model_info, 'name', model_info.id),  # Use name if available, fallback to id
                "provider": getattr(model_info, 'provider', model_info.owned_by),  # Use provider if available, fallback to owned_by
                "capabilities": model_info.capabilities,
                "context_window": model_info.context_window,
                "max_output_tokens": model_info.max_output_tokens,
                "supports_streaming": model_info.supports_streaming,
                "supports_function_calling": model_info.supports_function_calling
            }
            # Include tasks field if present
            if model_info.tasks:
                model_dict["tasks"] = model_info.tasks
            models.append(model_dict)
        
        # Update cache
        _models_cache["data"] = models
        _models_cache["cached_at"] = current_time
        
        return models
    except Exception as e:
        logger.error(f"Failed to fetch models from LLM service: {e}")
        
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


# Request/Response Models (API layer)
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


# Authentication: Public API endpoints should use require_api_key
# Internal API endpoints should use get_current_user from core.security

# Endpoints
@router.get("/models", response_model=ModelsResponse)
async def list_models(
    context: Dict[str, Any] = Depends(require_api_key),
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
        
        # Get models from cache or LLM service
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
    context: Dict[str, Any] = Depends(require_api_key),
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
    context: Dict[str, Any] = Depends(require_api_key),
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
        
            # Convert messages to LLM service format
            llm_messages = [LLMChatMessage(role=msg.role, content=msg.content) for msg in chat_request.messages]
            
            # Create LLM service request
            llm_request = ChatRequest(
                model=chat_request.model,
                messages=llm_messages,
                temperature=chat_request.temperature,
                max_tokens=chat_request.max_tokens,
                top_p=chat_request.top_p,
                frequency_penalty=chat_request.frequency_penalty,
                presence_penalty=chat_request.presence_penalty,
                stop=chat_request.stop,
                stream=chat_request.stream or False,
                user_id=str(context.get("user_id", "anonymous")),
                api_key_id=context.get("api_key_id", 0) if auth_type == "api_key" else 0
            )
            
            # Make request to LLM service
            llm_response = await llm_service.create_chat_completion(llm_request)
            
            # Convert LLM service response to API format
            response = {
                "id": llm_response.id,
                "object": llm_response.object,
                "created": llm_response.created,
                "model": llm_response.model,
                "choices": [
                    {
                        "index": choice.index,
                        "message": {
                            "role": choice.message.role,
                            "content": choice.message.content
                        },
                        "finish_reason": choice.finish_reason
                    }
                    for choice in llm_response.choices
                ],
                "usage": {
                    "prompt_tokens": llm_response.usage.prompt_tokens if llm_response.usage else 0,
                    "completion_tokens": llm_response.usage.completion_tokens if llm_response.usage else 0,
                    "total_tokens": llm_response.usage.total_tokens if llm_response.usage else 0
                } if llm_response.usage else {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }
            
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
    except SecurityError as e:
        logger.warning(f"Security error in chat completion: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security validation failed: {e.message}"
        )
    except ValidationError as e:
        logger.warning(f"Validation error in chat completion: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request validation failed: {e.message}"
        )
    except ProviderError as e:
        logger.error(f"Provider error in chat completion: {e}")
        if "rate limit" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM service temporarily unavailable"
            )
    except LLMError as e:
        logger.error(f"LLM service error in chat completion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM service error"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating chat completion: {e}")
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
        
            # Create LLM service request
            llm_request = LLMEmbeddingRequest(
                model=request.model,
                input=request.input,
                encoding_format=request.encoding_format,
                user_id=str(context["user_id"]),
                api_key_id=context["api_key_id"]
            )
            
            # Make request to LLM service
            llm_response = await llm_service.create_embedding(llm_request)
            
            # Convert LLM service response to API format
            response = {
                "object": llm_response.object,
                "data": [
                    {
                        "object": emb.object,
                        "index": emb.index,
                        "embedding": emb.embedding
                    }
                    for emb in llm_response.data
                ],
                "model": llm_response.model,
                "usage": {
                    "prompt_tokens": llm_response.usage.prompt_tokens if llm_response.usage else 0,
                    "total_tokens": llm_response.usage.total_tokens if llm_response.usage else 0
                } if llm_response.usage else {
                    "prompt_tokens": int(estimated_tokens),
                    "total_tokens": int(estimated_tokens)
                }
            }
            
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
    except SecurityError as e:
        logger.warning(f"Security error in embedding: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security validation failed: {e.message}"
        )
    except ValidationError as e:
        logger.warning(f"Validation error in embedding: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request validation failed: {e.message}"
        )
    except ProviderError as e:
        logger.error(f"Provider error in embedding: {e}")
        if "rate limit" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM service temporarily unavailable"
            )
    except LLMError as e:
        logger.error(f"LLM service error in embedding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM service error"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating embedding: {e}")
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
        health_summary = llm_service.get_health_summary()
        provider_status = await llm_service.get_provider_status()
        
        # Determine overall health
        overall_status = "healthy"
        if health_summary["service_status"] != "healthy":
            overall_status = "degraded"
        
        for provider, status in provider_status.items():
            if status.status == "unavailable":
                overall_status = "degraded"
                break
        
        return {
            "status": overall_status,
            "service": "LLM Service",
            "service_status": health_summary,
            "provider_status": {name: {
                "status": status.status,
                "latency_ms": status.latency_ms,
                "error_message": status.error_message
            } for name, status in provider_status.items()},
            "user_id": context["user_id"],
            "api_key_name": context["api_key_name"]
        }
    except Exception as e:
        logger.error(f"LLM health check error: {e}")
        return {
            "status": "unhealthy",
            "service": "LLM Service",
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
    context: Dict[str, Any] = Depends(require_api_key),
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


# Generic endpoint for additional LLM service functionality
@router.get("/metrics")
async def get_llm_metrics(
    context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Get LLM service metrics (admin only)"""
    try:
        # Check for admin permissions
        auth_service = APIKeyAuthService(db)
        if not await auth_service.check_scope_permission(context, "admin.metrics"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin permissions required to view metrics"
            )
        
        metrics = llm_service.get_metrics()
        return {
            "object": "llm_metrics",
            "data": {
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "security_blocked_requests": metrics.security_blocked_requests,
                "average_latency_ms": metrics.average_latency_ms,
                "average_risk_score": metrics.average_risk_score,
                "provider_metrics": metrics.provider_metrics,
                "last_updated": metrics.last_updated.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting LLM metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get LLM metrics"
        )


@router.get("/providers/status")
async def get_provider_status(
    context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Get status of all LLM providers"""
    try:
        auth_service = APIKeyAuthService(db)
        if not await auth_service.check_scope_permission(context, "admin.status"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin permissions required to view provider status"
            )
        
        provider_status = await llm_service.get_provider_status()
        return {
            "object": "provider_status",
            "data": {
                name: {
                    "provider": status.provider,
                    "status": status.status,
                    "latency_ms": status.latency_ms,
                    "success_rate": status.success_rate,
                    "last_check": status.last_check.isoformat(),
                    "error_message": status.error_message,
                    "models_available": status.models_available
                }
                for name, status in provider_status.items()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get provider status"
        )