"""
Conversations API Endpoints

OpenAI-compatible Conversations API for managing multi-turn conversations.
"""

import logging
import secrets
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from app.db.database import get_db
from app.models.conversation import Conversation
from app.services.api_key_auth import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================

class ConversationCreateRequest(BaseModel):
    """Request to create a conversation"""
    metadata: Optional[Dict[str, Any]] = None


class ConversationResponse(BaseModel):
    """Conversation response"""
    id: str
    object: str = "conversation"
    items: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None
    created_at: int
    updated_at: int


class ConversationListResponse(BaseModel):
    """List of conversations"""
    object: str = "list"
    data: List[ConversationResponse]
    has_more: bool = False
    first_id: Optional[str] = None
    last_id: Optional[str] = None


class ConversationItemsRequest(BaseModel):
    """Request to add items to conversation"""
    items: List[Dict[str, Any]]


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Conversation",
    description="Create a new conversation for multi-turn interactions.",
    tags=["Conversations API"]
)
async def create_conversation(
    request: ConversationCreateRequest,
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    """Create a new conversation.

    Args:
        request: Conversation creation request
        api_key_context: API key authentication context
        db: Database session

    Returns:
        Created conversation

    Raises:
        HTTPException: If creation fails
    """
    try:
        user = api_key_context.get("user")
        api_key = api_key_context.get("api_key")

        # Generate conversation ID
        conv_id = f"conv_{int(time.time() * 1000)}_{secrets.token_hex(4)}"

        # Create conversation
        conversation = Conversation(
            id=conv_id,
            user_id=user.id,
            api_key_id=api_key.id,
            items=[],
            conversation_metadata=request.metadata
        )

        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

        logger.info(f"Created conversation {conv_id}")

        return ConversationResponse(**conversation.to_dict())

    except Exception as e:
        logger.error(f"Error creating conversation: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create conversation: {str(e)}"
        )


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Conversations",
    description="List all conversations for the authenticated user.",
    tags=["Conversations API"]
)
async def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    after: Optional[str] = Query(default=None),
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
) -> ConversationListResponse:
    """List conversations.

    Args:
        limit: Maximum number of conversations to return
        after: Cursor for pagination
        api_key_context: API key authentication context
        db: Database session

    Returns:
        List of conversations
    """
    try:
        user = api_key_context.get("user")

        # Build query
        stmt = select(Conversation).where(
            Conversation.user_id == user.id
        ).order_by(Conversation.created_at.desc()).limit(limit + 1)

        # Apply cursor if provided
        if after:
            stmt = stmt.where(Conversation.id < after)

        result = await db.execute(stmt)
        conversations = result.scalars().all()

        # Check if there are more results
        has_more = len(conversations) > limit
        if has_more:
            conversations = conversations[:limit]

        # Convert to response
        data = [ConversationResponse(**conv.to_dict()) for conv in conversations]

        return ConversationListResponse(
            object="list",
            data=data,
            has_more=has_more,
            first_id=data[0].id if data else None,
            last_id=data[-1].id if data else None
        )

    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list conversations: {str(e)}"
        )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Conversation",
    description="Get a conversation by ID.",
    tags=["Conversations API"]
)
async def get_conversation(
    conversation_id: str,
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    """Get a conversation by ID.

    Args:
        conversation_id: Conversation ID
        api_key_context: API key authentication context
        db: Database session

    Returns:
        Conversation

    Raises:
        HTTPException: If conversation not found
    """
    try:
        user = api_key_context.get("user")

        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found"
            )

        return ConversationResponse(**conversation.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation: {str(e)}"
        )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Conversation",
    description="Delete a conversation by ID.",
    tags=["Conversations API"]
)
async def delete_conversation(
    conversation_id: str,
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Delete a conversation.

    Args:
        conversation_id: Conversation ID
        api_key_context: API key authentication context
        db: Database session

    Raises:
        HTTPException: If conversation not found
    """
    try:
        user = api_key_context.get("user")

        stmt = delete(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        )
        result = await db.execute(stmt)
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found"
            )

        logger.info(f"Deleted conversation {conversation_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversation: {str(e)}"
        )


@router.post(
    "/conversations/{conversation_id}/items",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Add Items to Conversation",
    description="Add items to a conversation.",
    tags=["Conversations API"]
)
async def add_conversation_items(
    conversation_id: str,
    request: ConversationItemsRequest,
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    """Add items to a conversation.

    Args:
        conversation_id: Conversation ID
        request: Items to add
        api_key_context: API key authentication context
        db: Database session

    Returns:
        Updated conversation

    Raises:
        HTTPException: If conversation not found
    """
    try:
        user = api_key_context.get("user")

        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found"
            )

        # Add items
        conversation.add_items(request.items)
        await db.commit()
        await db.refresh(conversation)

        logger.info(f"Added {len(request.items)} items to conversation {conversation_id}")

        return ConversationResponse(**conversation.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding items to conversation: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add items: {str(e)}"
        )


@router.get(
    "/conversations/{conversation_id}/items",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="List Conversation Items",
    description="Get all items from a conversation.",
    tags=["Conversations API"]
)
async def list_conversation_items(
    conversation_id: str,
    api_key_context: Dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get all items from a conversation.

    Args:
        conversation_id: Conversation ID
        api_key_context: API key authentication context
        db: Database session

    Returns:
        List of conversation items

    Raises:
        HTTPException: If conversation not found
    """
    try:
        user = api_key_context.get("user")

        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found"
            )

        return conversation.items or []

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing conversation items: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list items: {str(e)}"
        )
