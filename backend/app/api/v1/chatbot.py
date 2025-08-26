"""
Chatbot API endpoints
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import datetime

from app.db.database import get_db
from app.models.chatbot import ChatbotInstance, ChatbotConversation, ChatbotMessage, ChatbotAnalytics
from app.core.logging import log_api_request
from app.services.module_manager import module_manager
from app.core.security import get_current_user
from app.models.user import User
from app.services.api_key_auth import get_api_key_auth
from app.models.api_key import APIKey
from app.services.conversation_service import ConversationService

router = APIRouter()


class ChatbotCreateRequest(BaseModel):
    name: str
    chatbot_type: str = "assistant"
    model: str = "gpt-3.5-turbo"
    system_prompt: str = ""
    use_rag: bool = False
    rag_collection: Optional[str] = None
    rag_top_k: int = 5
    temperature: float = 0.7
    max_tokens: int = 1000
    memory_length: int = 10
    fallback_responses: List[str] = []


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


# OpenAI-compatible models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class ChatbotChatCompletionRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="List of messages")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(None, description="Temperature for sampling")
    top_p: Optional[float] = Field(None, description="Top-p sampling parameter")
    frequency_penalty: Optional[float] = Field(None, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(None, description="Presence penalty")
    stop: Optional[List[str]] = Field(None, description="Stop sequences")
    stream: Optional[bool] = Field(False, description="Stream response")


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class ChatUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatbotChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: ChatUsage


@router.get("/list")
@router.get("/instances") 
async def list_chatbots(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of all chatbots for the current user"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("list_chatbots", {"user_id": user_id})
    
    try:
        # Query chatbots created by the current user
        result = await db.execute(
            select(ChatbotInstance)
            .where(ChatbotInstance.created_by == str(user_id))
            .order_by(ChatbotInstance.created_at.desc())
        )
        chatbots = result.scalars().all()
        
        chatbot_list = []
        for chatbot in chatbots:
            chatbot_dict = {
                "id": chatbot.id,
                "name": chatbot.name,
                "description": chatbot.description,
                "config": chatbot.config,
                "created_by": chatbot.created_by,
                "created_at": chatbot.created_at.isoformat() if chatbot.created_at else None,
                "updated_at": chatbot.updated_at.isoformat() if chatbot.updated_at else None,
                "is_active": chatbot.is_active
            }
            chatbot_list.append(chatbot_dict)
        
        return chatbot_list
        
    except Exception as e:
        log_api_request("list_chatbots_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to fetch chatbots: {str(e)}")


@router.post("/create")
async def create_chatbot(
    request: ChatbotCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new chatbot instance"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("create_chatbot", {
        "user_id": user_id,
        "chatbot_name": request.name,
        "chatbot_type": request.chatbot_type
    })
    
    try:
        # Get the chatbot module 
        chatbot_module = module_manager.get_module("chatbot")
        if not chatbot_module:
            raise HTTPException(status_code=500, detail="Chatbot module not available")
        
        # Import needed types
        from modules.chatbot.main import ChatbotConfig
        
        # Create chatbot config object
        config = ChatbotConfig(
            name=request.name,
            chatbot_type=request.chatbot_type,
            model=request.model,
            system_prompt=request.system_prompt,
            use_rag=request.use_rag,
            rag_collection=request.rag_collection,
            rag_top_k=request.rag_top_k,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            memory_length=request.memory_length,
            fallback_responses=request.fallback_responses
        )
        
        # Use sync database session for module compatibility
        from app.db.database import SessionLocal
        sync_db = SessionLocal()
        
        try:
            # Use the chatbot module's create method (which handles default prompts)
            chatbot = await chatbot_module.create_chatbot(config, str(user_id), sync_db)
        finally:
            sync_db.close()
        
        # Return the created chatbot
        return {
            "id": chatbot.id,
            "name": chatbot.name,
            "description": f"AI chatbot of type {request.chatbot_type}",
            "config": chatbot.config.__dict__,
            "created_by": chatbot.created_by,
            "created_at": chatbot.created_at.isoformat() if chatbot.created_at else None,
            "updated_at": chatbot.updated_at.isoformat() if chatbot.updated_at else None,
            "is_active": chatbot.is_active
        }
        
    except Exception as e:
        await db.rollback()
        log_api_request("create_chatbot_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to create chatbot: {str(e)}")


@router.put("/update/{chatbot_id}")
async def update_chatbot(
    chatbot_id: str,
    request: ChatbotCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing chatbot instance"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("update_chatbot", {
        "user_id": user_id,
        "chatbot_id": chatbot_id,
        "chatbot_name": request.name
    })
    
    try:
        # Get existing chatbot and verify ownership
        result = await db.execute(
            select(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
            .where(ChatbotInstance.created_by == str(user_id))
        )
        chatbot = result.scalar_one_or_none()
        
        if not chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found or access denied")
        
        # Update chatbot configuration
        config = {
            "name": request.name,
            "chatbot_type": request.chatbot_type,
            "model": request.model,
            "system_prompt": request.system_prompt,
            "use_rag": request.use_rag,
            "rag_collection": request.rag_collection,
            "rag_top_k": request.rag_top_k,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "memory_length": request.memory_length,
            "fallback_responses": request.fallback_responses
        }
        
        # Update the chatbot
        await db.execute(
            update(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
            .values(
                name=request.name,
                config=config,
                updated_at=datetime.utcnow()
            )
        )
        
        await db.commit()
        
        # Return updated chatbot
        updated_result = await db.execute(
            select(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
        )
        updated_chatbot = updated_result.scalar_one()
        
        return {
            "id": updated_chatbot.id,
            "name": updated_chatbot.name,
            "description": updated_chatbot.description,
            "config": updated_chatbot.config,
            "created_by": updated_chatbot.created_by,
            "created_at": updated_chatbot.created_at.isoformat() if updated_chatbot.created_at else None,
            "updated_at": updated_chatbot.updated_at.isoformat() if updated_chatbot.updated_at else None,
            "is_active": updated_chatbot.is_active
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log_api_request("update_chatbot_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to update chatbot: {str(e)}")


@router.post("/chat/{chatbot_id}")
async def chat_with_chatbot(
    chatbot_id: str,
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a message to a chatbot and get a response"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("chat_with_chatbot", {
        "user_id": user_id,
        "chatbot_id": chatbot_id,
        "message_length": len(request.message)
    })
    
    try:
        # Get the chatbot instance
        result = await db.execute(
            select(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
            .where(ChatbotInstance.created_by == str(user_id))
        )
        chatbot = result.scalar_one_or_none()
        
        if not chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found")
        
        if not chatbot.is_active:
            raise HTTPException(status_code=400, detail="Chatbot is not active")
        
        # Initialize conversation service
        conversation_service = ConversationService(db)
        
        # Get or create conversation
        conversation = await conversation_service.get_or_create_conversation(
            chatbot_id=chatbot_id,
            user_id=str(user_id),
            conversation_id=request.conversation_id
        )
        
        # Add user message to conversation
        await conversation_service.add_message(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            metadata={}
        )
        
        # Get chatbot module and generate response
        try:
            chatbot_module = module_manager.modules.get("chatbot")
            if not chatbot_module:
                raise HTTPException(status_code=500, detail="Chatbot module not available")
            
            # Load conversation history for context
            conversation_history = await conversation_service.get_conversation_history(
                conversation_id=conversation.id,
                limit=chatbot.config.get('memory_length', 10),
                include_system=False
            )
            
            # Use the chatbot module to generate a response
            response_data = await chatbot_module.chat(
                chatbot_config=chatbot.config,
                message=request.message,
                conversation_history=conversation_history,
                user_id=str(user_id)
            )
            
            response_content = response_data.get("response", "I'm sorry, I couldn't generate a response.")
            
        except Exception as e:
            # Use fallback response
            fallback_responses = chatbot.config.get("fallback_responses", [
                "I'm sorry, I'm having trouble processing your request right now."
            ])
            response_content = fallback_responses[0] if fallback_responses else "I'm sorry, I couldn't process your request."
        
        # Save assistant message using conversation service
        assistant_message = await conversation_service.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=response_content,
            metadata={},
            sources=response_data.get("sources")
        )
        
        return {
            "conversation_id": conversation.id,
            "response": response_content,
            "timestamp": assistant_message.timestamp.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log_api_request("chat_with_chatbot_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to process chat: {str(e)}")


@router.post("/{chatbot_id}/chat/completions", response_model=ChatbotChatCompletionResponse)
async def chatbot_chat_completions(
    chatbot_id: str,
    request: ChatbotChatCompletionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """OpenAI-compatible chat completions endpoint for chatbot"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("chatbot_chat_completions", {
        "user_id": user_id,
        "chatbot_id": chatbot_id,
        "messages_count": len(request.messages)
    })
    
    try:
        # Get the chatbot instance
        result = await db.execute(
            select(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
            .where(ChatbotInstance.created_by == str(user_id))
        )
        chatbot = result.scalar_one_or_none()
        
        if not chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found")
        
        if not chatbot.is_active:
            raise HTTPException(status_code=400, detail="Chatbot is not active")
        
        # Find the last user message to extract conversation context
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user message found in conversation")
        
        last_user_message = user_messages[-1].content
        
        # Initialize conversation service
        conversation_service = ConversationService(db)
        
        # For OpenAI format, we'll try to find an existing conversation or create a new one
        # We'll use a simple hash of the conversation messages as the conversation identifier
        import hashlib
        conv_hash = hashlib.md5(str([f"{msg.role}:{msg.content}" for msg in request.messages]).encode()).hexdigest()[:16]
        
        # Get or create conversation
        conversation = await conversation_service.get_or_create_conversation(
            chatbot_id=chatbot_id,
            user_id=str(user_id),
            conversation_id=conv_hash
        )
        
        # Build conversation history from the request messages (excluding system messages for now)
        conversation_history = []
        for msg in request.messages:
            if msg.role in ["user", "assistant"]:
                conversation_history.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Get chatbot module and generate response
        try:
            chatbot_module = module_manager.modules.get("chatbot")
            if not chatbot_module:
                raise HTTPException(status_code=500, detail="Chatbot module not available")
            
            # Merge chatbot config with request parameters
            effective_config = dict(chatbot.config)
            if request.temperature is not None:
                effective_config["temperature"] = request.temperature
            if request.max_tokens is not None:
                effective_config["max_tokens"] = request.max_tokens
            
            # Use the chatbot module to generate a response
            response_data = await chatbot_module.chat(
                chatbot_config=effective_config,
                message=last_user_message,
                conversation_history=conversation_history,
                user_id=str(user_id)
            )
            
            response_content = response_data.get("response", "I'm sorry, I couldn't generate a response.")
            
        except Exception as e:
            # Use fallback response
            fallback_responses = chatbot.config.get("fallback_responses", [
                "I'm sorry, I'm having trouble processing your request right now."
            ])
            response_content = fallback_responses[0] if fallback_responses else "I'm sorry, I couldn't process your request."
        
        # Save the conversation messages
        for msg in request.messages:
            if msg.role == "user":  # Only save the new user message
                await conversation_service.add_message(
                    conversation_id=conversation.id,
                    role=msg.role,
                    content=msg.content,
                    metadata={}
                )
        
        # Save assistant message
        assistant_message = await conversation_service.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=response_content,
            metadata={},
            sources=response_data.get("sources")
        )
        
        # Calculate usage (simple approximation)
        prompt_tokens = sum(len(msg.content.split()) for msg in request.messages)
        completion_tokens = len(response_content.split())
        total_tokens = prompt_tokens + completion_tokens
        
        # Create OpenAI-compatible response
        response_id = f"chatbot-{chatbot_id}-{int(time.time())}"
        
        return ChatbotChatCompletionResponse(
            id=response_id,
            object="chat.completion",
            created=int(time.time()),
            model=chatbot.config.get("model", "unknown"),
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=response_content),
                    finish_reason="stop"
                )
            ],
            usage=ChatUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log_api_request("chatbot_chat_completions_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to process chat completions: {str(e)}")


@router.get("/conversations/{chatbot_id}")
async def get_chatbot_conversations(
    chatbot_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversations for a chatbot"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("get_chatbot_conversations", {
        "user_id": user_id,
        "chatbot_id": chatbot_id
    })
    
    try:
        # Verify chatbot ownership
        chatbot_result = await db.execute(
            select(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
            .where(ChatbotInstance.created_by == str(user_id))
        )
        chatbot = chatbot_result.scalar_one_or_none()
        
        if not chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found")
        
        # Get conversations
        result = await db.execute(
            select(ChatbotConversation)
            .where(ChatbotConversation.chatbot_id == chatbot_id)
            .where(ChatbotConversation.user_id == str(user_id))
            .order_by(ChatbotConversation.updated_at.desc())
        )
        conversations = result.scalars().all()
        
        conversation_list = []
        for conv in conversations:
            conversation_list.append({
                "id": conv.id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                "is_active": conv.is_active
            })
        
        return conversation_list
        
    except HTTPException:
        raise
    except Exception as e:
        log_api_request("get_chatbot_conversations_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversations: {str(e)}")


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a conversation"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("get_conversation_messages", {
        "user_id": user_id,
        "conversation_id": conversation_id
    })
    
    try:
        # Verify conversation ownership
        conv_result = await db.execute(
            select(ChatbotConversation)
            .where(ChatbotConversation.id == conversation_id)
            .where(ChatbotConversation.user_id == str(user_id))
        )
        conversation = conv_result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get messages
        result = await db.execute(
            select(ChatbotMessage)
            .where(ChatbotMessage.conversation_id == conversation_id)
            .order_by(ChatbotMessage.timestamp.asc())
        )
        messages = result.scalars().all()
        
        message_list = []
        for msg in messages:
            message_list.append({
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "metadata": msg.message_metadata,
                "sources": msg.sources
            })
        
        return message_list
        
    except HTTPException:
        raise
    except Exception as e:
        log_api_request("get_conversation_messages_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to fetch messages: {str(e)}")


@router.delete("/delete/{chatbot_id}")
async def delete_chatbot(
    chatbot_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a chatbot and all associated conversations/messages"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("delete_chatbot", {
        "user_id": user_id,
        "chatbot_id": chatbot_id
    })
    
    try:
        # Get existing chatbot and verify ownership
        result = await db.execute(
            select(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
            .where(ChatbotInstance.created_by == str(user_id))
        )
        chatbot = result.scalar_one_or_none()
        
        if not chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found or access denied")
        
        # Delete all messages associated with this chatbot's conversations
        await db.execute(
            delete(ChatbotMessage)
            .where(ChatbotMessage.conversation_id.in_(
                select(ChatbotConversation.id)
                .where(ChatbotConversation.chatbot_id == chatbot_id)
            ))
        )
        
        # Delete all conversations associated with this chatbot  
        await db.execute(
            delete(ChatbotConversation)
            .where(ChatbotConversation.chatbot_id == chatbot_id)
        )
        
        # Delete any analytics data
        await db.execute(
            delete(ChatbotAnalytics)
            .where(ChatbotAnalytics.chatbot_id == chatbot_id)
        )
        
        # Finally, delete the chatbot itself
        await db.execute(
            delete(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
        )
        
        await db.commit()
        
        return {"message": "Chatbot deleted successfully", "chatbot_id": chatbot_id}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log_api_request("delete_chatbot_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to delete chatbot: {str(e)}")


@router.post("/external/{chatbot_id}/chat")
async def external_chat_with_chatbot(
    chatbot_id: str,
    request: ChatRequest,
    api_key: APIKey = Depends(get_api_key_auth),
    db: AsyncSession = Depends(get_db)
):
    """External API endpoint for chatbot access with API key authentication"""
    log_api_request("external_chat_with_chatbot", {
        "chatbot_id": chatbot_id,
        "api_key_id": api_key.id,
        "message_length": len(request.message)
    })
    
    try:
        # Check if API key can access this chatbot
        if not api_key.can_access_chatbot(chatbot_id):
            raise HTTPException(status_code=403, detail="API key not authorized for this chatbot")
        
        # Get the chatbot instance
        result = await db.execute(
            select(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
        )
        chatbot = result.scalar_one_or_none()
        
        if not chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found")
        
        if not chatbot.is_active:
            raise HTTPException(status_code=400, detail="Chatbot is not active")
        
        # Initialize conversation service
        conversation_service = ConversationService(db)
        
        # Get or create conversation with API key context
        conversation = await conversation_service.get_or_create_conversation(
            chatbot_id=chatbot_id,
            user_id=f"api_key_{api_key.id}",
            conversation_id=request.conversation_id,
            title=f"API Chat {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        )
        
        # Add API key metadata to conversation context if new
        if not conversation.context_data.get("api_key_id"):
            conversation.context_data = {"api_key_id": api_key.id}
            await db.commit()
        
        # Add user message to conversation
        await conversation_service.add_message(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            metadata={"api_key_id": api_key.id}
        )
        
        # Get chatbot module and generate response
        try:
            chatbot_module = module_manager.modules.get("chatbot")
            if not chatbot_module:
                raise HTTPException(status_code=500, detail="Chatbot module not available")
            
            # Load conversation history for context
            conversation_history = await conversation_service.get_conversation_history(
                conversation_id=conversation.id,
                limit=chatbot.config.get('memory_length', 10),
                include_system=False
            )
            
            # Use the chatbot module to generate a response
            response_data = await chatbot_module.chat(
                chatbot_config=chatbot.config,
                message=request.message,
                conversation_history=conversation_history,
                user_id=f"api_key_{api_key.id}"
            )
            
            response_content = response_data.get("response", "I'm sorry, I couldn't generate a response.")
            sources = response_data.get("sources")
            
        except Exception as e:
            # Use fallback response
            fallback_responses = chatbot.config.get("fallback_responses", [
                "I'm sorry, I'm having trouble processing your request right now."
            ])
            response_content = fallback_responses[0] if fallback_responses else "I'm sorry, I couldn't process your request."
            sources = None
        
        # Save assistant message using conversation service
        assistant_message = await conversation_service.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=response_content,
            metadata={"api_key_id": api_key.id},
            sources=sources
        )
        
        # Update API key usage stats
        api_key.update_usage(tokens_used=len(request.message) + len(response_content), cost_cents=0)
        await db.commit()
        
        return {
            "conversation_id": conversation.id,
            "response": response_content,
            "sources": sources,
            "timestamp": assistant_message.timestamp.isoformat(),
            "chatbot_id": chatbot_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log_api_request("external_chat_with_chatbot_error", {"error": str(e), "chatbot_id": chatbot_id})
        raise HTTPException(status_code=500, detail=f"Failed to process chat: {str(e)}")


@router.post("/external/{chatbot_id}/chat/completions", response_model=ChatbotChatCompletionResponse)
async def external_chatbot_chat_completions(
    chatbot_id: str,
    request: ChatbotChatCompletionRequest,
    api_key: APIKey = Depends(get_api_key_auth),
    db: AsyncSession = Depends(get_db)
):
    """External OpenAI-compatible chat completions endpoint for chatbot with API key authentication"""
    log_api_request("external_chatbot_chat_completions", {
        "chatbot_id": chatbot_id,
        "api_key_id": api_key.id,
        "messages_count": len(request.messages)
    })
    
    try:
        # Check if API key can access this chatbot
        if not api_key.can_access_chatbot(chatbot_id):
            raise HTTPException(status_code=403, detail="API key not authorized for this chatbot")
        
        # Get the chatbot instance
        result = await db.execute(
            select(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
        )
        chatbot = result.scalar_one_or_none()
        
        if not chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found")
        
        if not chatbot.is_active:
            raise HTTPException(status_code=400, detail="Chatbot is not active")
        
        # Find the last user message to extract conversation context
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user message found in conversation")
        
        last_user_message = user_messages[-1].content
        
        # Initialize conversation service
        conversation_service = ConversationService(db)
        
        # For OpenAI format, we'll try to find an existing conversation or create a new one
        # We'll use a simple hash of the conversation messages as the conversation identifier
        import hashlib
        conv_hash = hashlib.md5(str([f"{msg.role}:{msg.content}" for msg in request.messages]).encode()).hexdigest()[:16]
        
        # Get or create conversation with API key context
        conversation = await conversation_service.get_or_create_conversation(
            chatbot_id=chatbot_id,
            user_id=f"api_key_{api_key.id}",
            conversation_id=conv_hash,
            title=f"API Chat {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        )
        
        # Add API key metadata to conversation context if new
        if not conversation.context_data.get("api_key_id"):
            conversation.context_data = {"api_key_id": api_key.id}
            await db.commit()
        
        # Build conversation history from the request messages
        conversation_history = []
        for msg in request.messages:
            if msg.role in ["user", "assistant"]:
                conversation_history.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Get chatbot module and generate response
        try:
            chatbot_module = module_manager.modules.get("chatbot")
            if not chatbot_module:
                raise HTTPException(status_code=500, detail="Chatbot module not available")
            
            # Merge chatbot config with request parameters
            effective_config = dict(chatbot.config)
            if request.temperature is not None:
                effective_config["temperature"] = request.temperature
            if request.max_tokens is not None:
                effective_config["max_tokens"] = request.max_tokens
            
            # Use the chatbot module to generate a response
            response_data = await chatbot_module.chat(
                chatbot_config=effective_config,
                message=last_user_message,
                conversation_history=conversation_history,
                user_id=f"api_key_{api_key.id}"
            )
            
            response_content = response_data.get("response", "I'm sorry, I couldn't generate a response.")
            sources = response_data.get("sources")
            
        except Exception as e:
            # Use fallback response
            fallback_responses = chatbot.config.get("fallback_responses", [
                "I'm sorry, I'm having trouble processing your request right now."
            ])
            response_content = fallback_responses[0] if fallback_responses else "I'm sorry, I couldn't process your request."
            sources = None
        
        # Save the conversation messages
        for msg in request.messages:
            if msg.role == "user":  # Only save the new user message
                await conversation_service.add_message(
                    conversation_id=conversation.id,
                    role=msg.role,
                    content=msg.content,
                    metadata={"api_key_id": api_key.id}
                )
        
        # Save assistant message using conversation service
        assistant_message = await conversation_service.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=response_content,
            metadata={"api_key_id": api_key.id},
            sources=sources
        )
        
        # Update API key usage stats
        prompt_tokens = sum(len(msg.content.split()) for msg in request.messages)
        completion_tokens = len(response_content.split())
        total_tokens = prompt_tokens + completion_tokens
        
        api_key.update_usage(tokens_used=total_tokens, cost_cents=0)
        await db.commit()
        
        # Create OpenAI-compatible response
        response_id = f"chatbot-{chatbot_id}-{int(time.time())}"
        
        return ChatbotChatCompletionResponse(
            id=response_id,
            object="chat.completion",
            created=int(time.time()),
            model=chatbot.config.get("model", "unknown"),
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=response_content),
                    finish_reason="stop"
                )
            ],
            usage=ChatUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log_api_request("external_chatbot_chat_completions_error", {"error": str(e), "chatbot_id": chatbot_id})
        raise HTTPException(status_code=500, detail=f"Failed to process chat completions: {str(e)}")


@router.post("/{chatbot_id}/api-key")
async def create_chatbot_api_key(
    chatbot_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create an API key for a specific chatbot"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("create_chatbot_api_key", {
        "user_id": user_id,
        "chatbot_id": chatbot_id
    })
    
    try:
        # Get existing chatbot and verify ownership
        result = await db.execute(
            select(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
            .where(ChatbotInstance.created_by == str(user_id))
        )
        chatbot = result.scalar_one_or_none()
        
        if not chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found or access denied")
        
        # Generate API key
        from app.api.v1.api_keys import generate_api_key
        full_key, key_hash = generate_api_key()
        key_prefix = full_key[:8]
        
        # Create chatbot-specific API key
        new_api_key = APIKey.create_chatbot_key(
            user_id=user_id,
            name=f"{chatbot.name} API Key",
            key_hash=key_hash,
            key_prefix=key_prefix,
            chatbot_id=chatbot_id,
            chatbot_name=chatbot.name
        )
        
        db.add(new_api_key)
        await db.commit()
        await db.refresh(new_api_key)
        
        return {
            "api_key_id": new_api_key.id,
            "name": new_api_key.name,
            "key_prefix": new_api_key.key_prefix + "...",
            "secret_key": full_key,  # Only returned on creation
            "chatbot_id": chatbot_id,
            "chatbot_name": chatbot.name,
            "endpoint": f"/api/v1/chatbot/external/{chatbot_id}/chat/completions",
            "scopes": new_api_key.scopes,
            "rate_limit_per_minute": new_api_key.rate_limit_per_minute,
            "created_at": new_api_key.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log_api_request("create_chatbot_api_key_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to create chatbot API key: {str(e)}")


@router.get("/{chatbot_id}/api-keys")
async def list_chatbot_api_keys(
    chatbot_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List API keys for a specific chatbot"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("list_chatbot_api_keys", {
        "user_id": user_id,
        "chatbot_id": chatbot_id
    })
    
    try:
        # Get existing chatbot and verify ownership
        result = await db.execute(
            select(ChatbotInstance)
            .where(ChatbotInstance.id == chatbot_id)
            .where(ChatbotInstance.created_by == str(user_id))
        )
        chatbot = result.scalar_one_or_none()
        
        if not chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found or access denied")
        
        # Get API keys that can access this chatbot
        api_keys_result = await db.execute(
            select(APIKey)
            .where(APIKey.user_id == user_id)
            .where(APIKey.allowed_chatbots.contains([chatbot_id]))
            .order_by(APIKey.created_at.desc())
        )
        api_keys = api_keys_result.scalars().all()
        
        api_key_list = []
        for api_key in api_keys:
            api_key_list.append({
                "id": api_key.id,
                "name": api_key.name,
                "key_prefix": api_key.key_prefix + "...",
                "is_active": api_key.is_active,
                "created_at": api_key.created_at.isoformat(),
                "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
                "total_requests": api_key.total_requests,
                "rate_limit_per_minute": api_key.rate_limit_per_minute,
                "scopes": api_key.scopes
            })
        
        return {
            "chatbot_id": chatbot_id,
            "chatbot_name": chatbot.name,
            "api_keys": api_key_list,
            "total": len(api_key_list)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_api_request("list_chatbot_api_keys_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to list chatbot API keys: {str(e)}")