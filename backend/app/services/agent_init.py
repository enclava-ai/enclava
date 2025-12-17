"""
Agent initialization utilities

Creates required database records for agent functionality.
"""
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.chatbot import ChatbotInstance
from app.db.database import async_session_factory

logger = logging.getLogger(__name__)

AGENT_CHATBOT_ID = "agent"


async def initialize_agent_chatbot_instance():
    """Create or update the special 'agent' chatbot instance.

    This is required for agent conversations to satisfy the foreign key
    constraint in chatbot_conversations table.

    The agent chatbot instance is a special marker that:
    - Has a fixed ID of "agent"
    - Is used for all agent-based conversations (not traditional chatbot instances)
    - Contains minimal configuration since agents use their own AgentConfig
    """
    async with async_session_factory() as db:
        try:
            # Check if agent instance already exists
            stmt = select(ChatbotInstance).where(ChatbotInstance.id == AGENT_CHATBOT_ID)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                logger.info("Agent chatbot instance already exists")
                return

            # Create new agent instance
            agent_instance = ChatbotInstance(
                id=AGENT_CHATBOT_ID,
                name="Agent",
                description="Special chatbot instance for agent-based conversations",
                config={
                    "type": "agent",
                    "description": "This is a system instance used for agent conversations"
                },
                created_by="system",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_active=True
            )

            db.add(agent_instance)
            await db.commit()
            logger.info(f"Created agent chatbot instance with ID '{AGENT_CHATBOT_ID}'")

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to initialize agent chatbot instance: {e}")
            raise
