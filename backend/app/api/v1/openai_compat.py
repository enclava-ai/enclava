"""
OpenAI-compatible API endpoints
Following the exact OpenAI API specification for compatibility with OpenAI clients
"""

import json
import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.llm import (
    ChatCompletionRequest,
    EmbeddingRequest,
    ModelInfo,
    ModelsResponse,
)
from app.api.v1.llm import create_chat_completion as llm_chat_completion
from app.api.v1.llm import create_embedding as llm_create_embedding
from app.api.v1.llm import (
    get_cached_models,
)
from app.core.config import settings
from app.db.database import get_db
from app.services.api_key_auth import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


def _test_mode_enabled() -> bool:
    return settings.TESTING or settings.LLM_TEST_MODE


def _test_models() -> List[Dict[str, Any]]:
    created = 1_700_000_000
    return [
        {
            "id": "test-model",
            "object": "model",
            "created": created,
            "owned_by": "enclava-test",
            "name": "test-model",
            "provider": "test",
            "capabilities": ["chat", "streaming", "function_calling"],
            "context_window": 8192,
            "max_output_tokens": 1024,
            "supports_streaming": True,
            "supports_function_calling": True,
        },
        {
            "id": "text-embedding-ada-002",
            "object": "model",
            "created": created,
            "owned_by": "enclava-test",
            "name": "text-embedding-ada-002",
            "provider": "test",
            "capabilities": ["embeddings"],
            "context_window": 8192,
            "max_output_tokens": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
        },
    ]


def _is_test_model(model: str, *, embeddings: bool = False) -> bool:
    allowed = {"test-model", "gpt-3.5-turbo", "gpt-4"}
    if embeddings:
        allowed.add("text-embedding-ada-002")
    return model in allowed


def _usage_for_messages(
    messages: List[Any], completion_tokens: int = 8
) -> Dict[str, int]:
    prompt_text = " ".join(
        getattr(message, "content", "") or "" for message in messages
    )
    prompt_tokens = max(1, len(prompt_text.split()))
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _test_chat_response(
    chat_request: ChatCompletionRequest, body: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    created = int(time.time())
    usage = _usage_for_messages(chat_request.messages)
    message = {
        "role": "assistant",
        "content": "Hello from Enclava test mode.",
    }
    functions = (body or {}).get("functions") or []
    if functions:
        message["function_call"] = {
            "name": functions[0].get("name", "test_function"),
            "arguments": "{}",
        }

    return {
        "id": f"chatcmpl-test-{created}",
        "object": "chat.completion",
        "created": created,
        "model": chat_request.model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "stop",
            }
        ],
        "usage": usage,
    }


async def _test_chat_stream(chat_request: ChatCompletionRequest):
    created = int(time.time())
    chunks = [
        {
            "id": f"chatcmpl-test-{created}",
            "object": "chat.completion.chunk",
            "created": created,
            "model": chat_request.model,
            "choices": [
                {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
            ],
        },
        {
            "id": f"chatcmpl-test-{created}",
            "object": "chat.completion.chunk",
            "created": created,
            "model": chat_request.model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": "Hello from Enclava test mode."},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": f"chatcmpl-test-{created}",
            "object": "chat.completion.chunk",
            "created": created,
            "model": chat_request.model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        },
    ]
    for chunk in chunks:
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"


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
        if _test_mode_enabled():
            return ModelsResponse(data=_test_models())

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
    context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Create chat completion - OpenAI compatible endpoint

    This endpoint follows the exact OpenAI API specification:
    POST /v1/chat/completions
    """
    body = await request_body.json()
    try:
        chat_request = ChatCompletionRequest(**body)
    except PydanticValidationError as e:
        return openai_error_response(str(e), "invalid_request_error", 400)

    if _test_mode_enabled():
        if not _is_test_model(chat_request.model):
            return openai_error_response(
                f"Model '{chat_request.model}' not found",
                "invalid_request_error",
                400,
                "model_not_found",
            )
        if chat_request.stream:
            return StreamingResponse(
                _test_chat_stream(chat_request),
                media_type="text/event-stream",
            )
        return _test_chat_response(chat_request, body)

    # Delegate to the existing LLM chat completions endpoint
    return await llm_chat_completion(request_body, chat_request, context, db)


@router.post("/embeddings")
async def create_embedding(
    request_body: Request,
    context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Create embedding - OpenAI compatible endpoint

    This endpoint follows the exact OpenAI API specification:
    POST /v1/embeddings
    """
    body = await request_body.json()
    try:
        request = EmbeddingRequest(**body)
    except PydanticValidationError as e:
        return openai_error_response(str(e), "invalid_request_error", 400)

    if _test_mode_enabled():
        if not _is_test_model(request.model, embeddings=True):
            return openai_error_response(
                f"Model '{request.model}' not found",
                "invalid_request_error",
                400,
                "model_not_found",
            )
        prompt_tokens = max(1, len(request.input.split()))
        return {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "index": 0,
                    "embedding": [0.01, 0.02, 0.03, 0.04],
                }
            ],
            "model": request.model,
            "usage": {"prompt_tokens": prompt_tokens, "total_tokens": prompt_tokens},
        }

    # Delegate to the existing LLM embeddings endpoint
    return await llm_create_embedding(request_body, request, context, db)


@router.post("/completions")
async def create_completion(
    request_body: Request,
    context: Dict[str, Any] = Depends(require_api_key),
):
    """Create legacy text completion - OpenAI compatible endpoint."""
    body = await request_body.json()
    model = body.get("model", "")

    if not _test_mode_enabled():
        return openai_error_response(
            "Legacy completions not supported", "invalid_request_error", 404
        )

    if not _is_test_model(model):
        return openai_error_response(
            f"Model '{model}' not found",
            "invalid_request_error",
            400,
            "model_not_found",
        )

    created = int(time.time())
    prompt = str(body.get("prompt", ""))
    prompt_tokens = max(1, len(prompt.split()))
    completion_tokens = 4
    return {
        "id": f"cmpl-test-{created}",
        "object": "text_completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "text": "Hello from Enclava test mode.",
                "index": 0,
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


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
