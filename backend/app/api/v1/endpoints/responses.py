"""
Responses API Endpoints

OpenAI-compatible Responses API for agentic interactions with tool execution.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.responses import ResponseCreateRequest, ResponseObject
from app.services.responses.responses_service import ResponsesService
from app.services.api_key_auth import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/responses",
    status_code=status.HTTP_200_OK,
    summary="Create Response",
    description="""
    Create a response with automatic tool execution.

    This endpoint:
    - Accepts either string input or structured items
    - Automatically executes tool calls in an agentic loop
    - Supports RAG (file_search), web_search, MCP, and custom tools
    - Enforces budget limits
    - Optionally stores responses for retrieval and chaining
    - Supports conversation threading and response chaining
    - Supports streaming with ?stream=true query parameter

    Compatible with OpenAI's Responses API format.
    """,
    tags=["Responses API"]
)
async def create_response(
    request: ResponseCreateRequest,
    stream: bool = Query(default=False, description="Enable streaming response"),
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a response with automatic tool execution.

    Args:
        request: Response creation request
        stream: Enable streaming response
        api_key_context: API key authentication context
        db: Database session

    Returns:
        ResponseObject or StreamingResponse with SSE events

    Raises:
        HTTPException: If budget exceeded, invalid request, or internal error
    """
    try:
        service = ResponsesService(db)

        # Handle streaming request
        if stream:
            async def event_generator():
                async for event in service.create_response_stream(request, api_key_context):
                    yield event

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"  # Disable nginx buffering
                }
            )

        # Handle non-streaming request
        response = await service.create_response(request, api_key_context)

        # Check if response failed
        if response.status == "failed":
            error = response.error or {}
            error_type = error.get("type", "internal_error")

            if error_type == "budget_exceeded":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=error.get("message", "Budget exceeded")
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error.get("message", "Internal server error")
                )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_response endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create response: {str(e)}"
        )


@router.get(
    "/responses/{response_id}",
    response_model=ResponseObject,
    status_code=status.HTTP_200_OK,
    summary="Get Response",
    description="""
    Retrieve a stored response by ID.

    Only returns responses owned by the authenticated user.
    Responses with store=false cannot be retrieved.
    """,
    tags=["Responses API"]
)
async def get_response(
    response_id: str,
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
) -> ResponseObject:
    """
    Get a stored response by ID.

    Args:
        response_id: Response ID
        api_key_context: API key authentication context
        db: Database session

    Returns:
        ResponseObject if found

    Raises:
        HTTPException: If response not found or access denied
    """
    try:
        user = api_key_context.get("user")

        service = ResponsesService(db)
        response = await service.get_response(response_id, user.id)

        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Response {response_id} not found"
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_response endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve response: {str(e)}"
        )
