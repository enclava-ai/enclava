"""
Conversation Service
Handles chatbot conversation management including history loading, 
message persistence, and conversation lifecycle.
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload
import logging

from app.models.chatbot import ChatbotConversation, ChatbotMessage, ChatbotInstance
from app.utils.exceptions import APIException

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing chatbot conversations and message history"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_conversation(
        self,
        chatbot_id: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> ChatbotConversation:
        """Get existing conversation or create a new one"""

        # If conversation_id provided, try to get existing conversation
        if conversation_id:
            stmt = select(ChatbotConversation).where(
                and_(
                    ChatbotConversation.id == conversation_id,
                    ChatbotConversation.chatbot_id == chatbot_id,
                    ChatbotConversation.user_id == user_id,
                    ChatbotConversation.is_active == True,
                )
            )
            result = await self.db.execute(stmt)
            conversation = result.scalar_one_or_none()

            if conversation:
                logger.info(f"Found existing conversation {conversation_id}")
                return conversation
            else:
                logger.warning(
                    f"Conversation {conversation_id} not found or not accessible"
                )

        # Create new conversation
        if not title:
            title = f"Chat {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

        conversation = ChatbotConversation(
            chatbot_id=chatbot_id,
            user_id=user_id,
            title=title,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
            context_data={},
        )

        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)

        logger.info(
            f"Created new conversation {conversation.id} for chatbot {chatbot_id}"
        )
        return conversation

    async def get_conversation_history(
        self, conversation_id: str, limit: int = 20, include_system: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Load conversation history for a conversation

        Args:
            conversation_id: ID of the conversation
            limit: Maximum number of messages to return (default 20)
            include_system: Whether to include system messages (default False)

        Returns:
            List of messages in chronological order (oldest first)
        """
        try:
            # Build query to get recent messages
            stmt = select(ChatbotMessage).where(
                ChatbotMessage.conversation_id == conversation_id
            )

            # Optionally exclude system messages
            if not include_system:
                stmt = stmt.where(ChatbotMessage.role != "system")

            # Order by timestamp descending and limit
            stmt = stmt.order_by(desc(ChatbotMessage.timestamp)).limit(limit)

            result = await self.db.execute(stmt)
            messages = result.scalars().all()

            # Convert to list and reverse to get chronological order (oldest first)
            history = []
            for msg in reversed(messages):
                history.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat()
                        if msg.timestamp
                        else None,
                        "metadata": msg.message_metadata or {},
                        "sources": msg.sources,
                    }
                )

            logger.info(
                f"Loaded {len(history)} messages for conversation {conversation_id}"
            )
            return history

        except Exception as e:
            logger.error(
                f"Failed to load conversation history for {conversation_id}: {e}"
            )
            return []  # Return empty list on error to avoid breaking chat

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> ChatbotMessage:
        """Add a message to a conversation"""

        if role not in ["user", "assistant", "system"]:
            raise ValueError(f"Invalid message role: {role}")

        message = ChatbotMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            message_metadata=metadata or {},
            sources=sources,
        )

        self.db.add(message)

        # Update conversation timestamp
        stmt = select(ChatbotConversation).where(
            ChatbotConversation.id == conversation_id
        )
        result = await self.db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if conversation:
            conversation.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(message)

        logger.info(f"Added {role} message to conversation {conversation_id}")
        return message

    async def get_conversation_stats(self, conversation_id: str) -> Dict[str, Any]:
        """Get statistics for a conversation"""

        # Count messages by role
        stmt = (
            select(ChatbotMessage.role, func.count(ChatbotMessage.id).label("count"))
            .where(ChatbotMessage.conversation_id == conversation_id)
            .group_by(ChatbotMessage.role)
        )

        result = await self.db.execute(stmt)
        role_counts = {row.role: row.count for row in result}

        # Get conversation info
        stmt = select(ChatbotConversation).where(
            ChatbotConversation.id == conversation_id
        )
        result = await self.db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise APIException(status_code=404, error_code="CONVERSATION_NOT_FOUND")

        return {
            "conversation_id": conversation_id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat()
            if conversation.created_at
            else None,
            "updated_at": conversation.updated_at.isoformat()
            if conversation.updated_at
            else None,
            "total_messages": sum(role_counts.values()),
            "user_messages": role_counts.get("user", 0),
            "assistant_messages": role_counts.get("assistant", 0),
            "system_messages": role_counts.get("system", 0),
        }

    async def archive_old_conversations(self, days_inactive: int = 30) -> int:
        """Archive conversations that haven't been used in specified days"""

        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)

        # Find conversations to archive
        stmt = select(ChatbotConversation).where(
            and_(
                ChatbotConversation.updated_at < cutoff_date,
                ChatbotConversation.is_active == True,
            )
        )

        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        archived_count = 0
        for conversation in conversations:
            conversation.is_active = False
            archived_count += 1

        if archived_count > 0:
            await self.db.commit()
            logger.info(f"Archived {archived_count} inactive conversations")

        return archived_count

    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Delete a conversation and all its messages"""

        # Verify ownership
        stmt = (
            select(ChatbotConversation)
            .where(
                and_(
                    ChatbotConversation.id == conversation_id,
                    ChatbotConversation.user_id == user_id,
                )
            )
            .options(selectinload(ChatbotConversation.messages))
        )

        result = await self.db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if not conversation:
            return False

        # Delete all messages first
        for message in conversation.messages:
            await self.db.delete(message)

        # Delete conversation
        await self.db.delete(conversation)
        await self.db.commit()

        logger.info(
            f"Deleted conversation {conversation_id} with {len(conversation.messages)} messages"
        )
        return True

    async def get_user_conversations(
        self,
        user_id: str,
        chatbot_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get list of conversations for a user"""

        stmt = select(ChatbotConversation).where(
            and_(
                ChatbotConversation.user_id == user_id,
                ChatbotConversation.is_active == True,
            )
        )

        if chatbot_id:
            stmt = stmt.where(ChatbotConversation.chatbot_id == chatbot_id)

        stmt = (
            stmt.order_by(desc(ChatbotConversation.updated_at))
            .offset(skip)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        conversation_list = []
        for conv in conversations:
            # Get message count
            msg_count_stmt = select(func.count(ChatbotMessage.id)).where(
                ChatbotMessage.conversation_id == conv.id
            )
            msg_count_result = await self.db.execute(msg_count_stmt)
            message_count = msg_count_result.scalar() or 0

            conversation_list.append(
                {
                    "id": conv.id,
                    "chatbot_id": conv.chatbot_id,
                    "title": conv.title,
                    "message_count": message_count,
                    "created_at": conv.created_at.isoformat()
                    if conv.created_at
                    else None,
                    "updated_at": conv.updated_at.isoformat()
                    if conv.updated_at
                    else None,
                    "context_data": conv.context_data or {},
                }
            )

        return conversation_list
