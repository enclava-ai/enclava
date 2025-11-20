"""
OpenAI-compatible API endpoints
Following the exact OpenAI API specification for compatibility with OpenAI clients
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.api_key_auth import require_api_key
from app.api.v1.llm import (
    get_cached_models,
    ModelsResponse,
    ModelInfo,
    ChatCompletionRequest,
    EmbeddingRequest,
    create_chat_completion as llm_chat_completion,
    create_embedding as llm_create_embedding,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def openai_error_response(
    message: str,
    error_type: str = "invalid_request_error",
    status_code: int = 400,
    code: str = None,
):
    """Create OpenAI-compatible error response"""
    error_data = {
        "error": {
            "message": message,
            "type": error_type,
        }
    }
    if code:
        error_data["error"]["code"] = code

    return JSONResponse(status_code=status_code, content=error_data)


@router.get("/models", response_model=ModelsResponse)
async def list_models(
    context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists the currently available models, and provides basic information about each one
    such as the owner and availability.

    This endpoint follows the exact OpenAI API specification:
    GET /v1/models
    """
    try:
        # Delegate to the existing LLM models endpoint
        from app.api.v1.llm import list_models as llm_list_models

        return await llm_list_models(context, db)
    except HTTPException as e:
        # Convert FastAPI HTTPException to OpenAI format
        if e.status_code == 401:
            return openai_error_response(
                "Invalid authentication credentials", "authentication_error", 401
            )
        elif e.status_code == 403:
            return openai_error_response(
                "Insufficient permissions", "permission_error", 403
            )
        else:
            return openai_error_response(str(e.detail), "api_error", e.status_code)
    except Exception as e:
        logger.error(f"Error in OpenAI models endpoint: {e}")
        return openai_error_response("Internal server error", "api_error", 500)


@router.post("/chat/completions")
async def create_chat_completion(
    request_body: Request,
    chat_request: ChatCompletionRequest,
    context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Create chat completion - OpenAI compatible endpoint

    This endpoint follows the exact OpenAI API specification:
    POST /v1/chat/completions
    """
    # Delegate to the existing LLM chat completions endpoint
    return await llm_chat_completion(request_body, chat_request, context, db)


@router.post("/embeddings")
async def create_embedding(
    request: EmbeddingRequest,
    context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Create embedding - OpenAI compatible endpoint

    This endpoint follows the exact OpenAI API specification:
    POST /v1/embeddings
    """
    # Delegate to the existing LLM embeddings endpoint
    return await llm_create_embedding(request, context, db)


@router.get("/models/{model_id}")
async def retrieve_model(
    model_id: str,
    context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve model information - OpenAI compatible endpoint

    This endpoint follows the exact OpenAI API specification:
    GET /v1/models/{model}
    """
    try:
        # Get all models and find the specific one
        models = await get_cached_models()

        # Filter models based on API key permissions
        api_key = context.get("api_key")
        if api_key and api_key.allowed_models:
            models = [
                model for model in models if model.get("id") in api_key.allowed_models
            ]

        # Find the specific model
        model = next((m for m in models if m.get("id") == model_id), None)

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_id}' not found",
            )

        return ModelInfo(
            id=model.get("id", model_id),
            object="model",
            created=model.get("created", 0),
            owned_by=model.get("owned_by", "system"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving model {model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model information",
        )
