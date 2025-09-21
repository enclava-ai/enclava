"""
Chatbot Module Implementation

Provides AI chatbot capabilities with:
- RAG integration for knowledge-based responses
- Custom prompts and personalities
- Conversation memory and context
- Workflow integration as building blocks
- UI-configurable settings
"""

import json
from pprint import pprint
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from pydantic import BaseModel, Field
from enum import Enum

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.llm.service import llm_service
from app.services.llm.models import ChatRequest as LLMChatRequest, ChatMessage as LLMChatMessage
from app.services.llm.exceptions import LLMError, ProviderError, SecurityError
from app.services.base_module import BaseModule, Permission
from app.models.user import User
from app.models.chatbot import ChatbotInstance as DBChatbotInstance, ChatbotConversation as DBConversation, ChatbotMessage as DBMessage, ChatbotAnalytics
from app.core.security import get_current_user
from app.db.database import get_db
from app.core.config import settings

# Import protocols for type hints and dependency injection
from ..protocols import RAGServiceProtocol
# Note: LiteLLMClientProtocol replaced with direct LLM service usage

logger = get_logger(__name__)


class ChatbotType(str, Enum):
    """Types of chatbot personalities"""
    ASSISTANT = "assistant"
    CUSTOMER_SUPPORT = "customer_support"
    TEACHER = "teacher" 
    RESEARCHER = "researcher"
    CREATIVE_WRITER = "creative_writer"
    CUSTOM = "custom"


class MessageRole(str, Enum):
    """Message roles in conversation"""
    USER = "user"
    ASSISTANT = "assistant" 
    SYSTEM = "system"


@dataclass
class ChatbotConfig:
    """Chatbot configuration"""
    name: str
    chatbot_type: str  # Changed from ChatbotType enum to str to allow custom types
    model: str
    rag_collection: Optional[str] = None
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 1000
    memory_length: int = 10  # Number of previous messages to remember
    use_rag: bool = False
    rag_top_k: int = 5
    fallback_responses: List[str] = None
    
    def __post_init__(self):
        if self.fallback_responses is None:
            self.fallback_responses = [
                "I'm not sure how to help with that. Could you please rephrase your question?",
                "I don't have enough information to answer that question accurately.",
                "That's outside my knowledge area. Is there something else I can help you with?"
            ]


class ChatMessage(BaseModel):
    """Individual chat message"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    sources: Optional[List[Dict[str, Any]]] = None


class Conversation(BaseModel):
    """Conversation state"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chatbot_id: str
    user_id: str
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """Chat completion request"""
    message: str
    conversation_id: Optional[str] = None
    chatbot_id: str
    use_rag: Optional[bool] = None
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """Chat completion response"""
    response: str
    conversation_id: str
    message_id: str
    sources: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatbotInstance(BaseModel):
    """Configured chatbot instance"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    config: ChatbotConfig
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True


class ChatbotModule(BaseModule):
    """Main chatbot module implementation"""
    
    def __init__(self, rag_service: Optional[RAGServiceProtocol] = None):
        super().__init__("chatbot")
        self.rag_module = rag_service  # Keep same name for compatibility
        self.db_session = None
        
        # System prompts will be loaded from database
        self.system_prompts = {}
    
    async def initialize(self, **kwargs):
        """Initialize the chatbot module"""
        await super().initialize(**kwargs)
        
        # Initialize the LLM service
        await llm_service.initialize()
        
        # Get RAG module dependency if not already injected
        if not self.rag_module:
            try:
                # Try to get RAG module from module manager
                from app.services.module_manager import module_manager
                if hasattr(module_manager, 'modules') and 'rag' in module_manager.modules:
                    self.rag_module = module_manager.modules['rag']
                    logger.info("RAG module injected from module manager")
            except Exception as e:
                logger.warning(f"Could not inject RAG module: {e}")
        
        # Load prompt templates from database
        await self._load_prompt_templates()
        
        logger.info("Chatbot module initialized")
        logger.info(f"LLM service available: {llm_service._initialized}")
        logger.info(f"RAG module available after init: {self.rag_module is not None}")
        logger.info(f"Loaded {len(self.system_prompts)} prompt templates")
    
    async def _ensure_dependencies(self):
        """Lazy load dependencies if not available"""
        # Ensure LLM service is initialized
        if not llm_service._initialized:
            await llm_service.initialize()
            logger.info("LLM service lazy loaded")
        
        if not self.rag_module:
            try:
                # Try to get RAG module from module manager
                from app.services.module_manager import module_manager
                if hasattr(module_manager, 'modules') and 'rag' in module_manager.modules:
                    self.rag_module = module_manager.modules['rag']
                    logger.info("RAG module lazy loaded from module manager")
            except Exception as e:
                logger.warning(f"Could not lazy load RAG module: {e}")
    
    async def _load_prompt_templates(self):
        """Load prompt templates from database"""
        try:
            from app.db.database import SessionLocal
            from app.models.prompt_template import PromptTemplate
            from sqlalchemy import select
            
            db = SessionLocal()
            try:
                result = db.execute(
                    select(PromptTemplate)
                    .where(PromptTemplate.is_active == True)
                )
                templates = result.scalars().all()
                
                for template in templates:
                    self.system_prompts[template.type_key] = template.system_prompt
                    
                logger.info(f"Loaded {len(self.system_prompts)} prompt templates from database")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.warning(f"Could not load prompt templates from database: {e}")
            # Fallback to hardcoded prompts
            self.system_prompts = {
                "assistant": "You are a helpful AI assistant. Provide accurate, concise, and friendly responses. Always aim to be helpful while being honest about your limitations.",
                "customer_support": "You are a professional customer support representative. Be empathetic, professional, and solution-focused in all interactions.",
                "teacher": "You are an experienced educational tutor. Break down complex concepts into understandable parts. Be patient, supportive, and encouraging.",
                "researcher": "You are a thorough research assistant with a focus on accuracy and evidence-based information.",
                "creative_writer": "You are an experienced creative writing mentor and storytelling expert.",
                "custom": "You are a helpful AI assistant. Your personality and behavior will be defined by custom instructions."
            }
    
    async def get_system_prompt_for_type(self, chatbot_type: str) -> str:
        """Get system prompt for a specific chatbot type"""
        if chatbot_type in self.system_prompts:
            return self.system_prompts[chatbot_type]
        
        # If not found, try to reload templates
        await self._load_prompt_templates()
        
        return self.system_prompts.get(chatbot_type, self.system_prompts.get("assistant", 
            "You are a helpful AI assistant. Provide accurate, concise, and friendly responses."))
    
    async def create_chatbot(self, config: ChatbotConfig, user_id: str, db: Session) -> ChatbotInstance:
        """Create a new chatbot instance"""
        
        # Set system prompt based on type if not provided or empty
        if not config.system_prompt or config.system_prompt.strip() == "":
            config.system_prompt = await self.get_system_prompt_for_type(config.chatbot_type)
        
        # Create database record
        db_chatbot = DBChatbotInstance(
            name=config.name,
            description=f"{config.chatbot_type.replace('_', ' ').title()} chatbot",
            config=config.__dict__,
            created_by=user_id
        )
        
        db.add(db_chatbot)
        db.commit()
        db.refresh(db_chatbot)
        
        # Convert to response model
        chatbot = ChatbotInstance(
            id=db_chatbot.id,
            name=db_chatbot.name,
            config=ChatbotConfig(**db_chatbot.config),
            created_by=db_chatbot.created_by,
            created_at=db_chatbot.created_at,
            updated_at=db_chatbot.updated_at,
            is_active=db_chatbot.is_active
        )
        
        logger.info(f"Created new chatbot: {chatbot.name} ({chatbot.id})")
        return chatbot
    
    async def chat_completion(self, request: ChatRequest, user_id: str, db: Session) -> ChatResponse:
        """Generate chat completion response"""
        
        # Get chatbot configuration from database
        db_chatbot = db.query(DBChatbotInstance).filter(DBChatbotInstance.id == request.chatbot_id).first()
        if not db_chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found")
        
        chatbot_config = ChatbotConfig(**db_chatbot.config)
        
        # Get or create conversation
        conversation = await self._get_or_create_conversation(
            request.conversation_id, request.chatbot_id, user_id, db
        )
        
        # Create user message
        user_message = DBMessage(
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            content=request.message
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)
        
        logger.info(f"Created user message with ID {user_message.id} for conversation {conversation.id}")
        
        try:
            # Force the session to see the committed changes
            db.expire_all()
            
            # Get conversation history for context - includes the current message we just created
            # Fetch up to memory_length pairs of messages (user + assistant)
            # The +1 ensures we include the current message if we're at the limit
            messages = db.query(DBMessage).filter(
                DBMessage.conversation_id == conversation.id
            ).order_by(DBMessage.timestamp.desc()).limit(chatbot_config.memory_length * 2 + 1).all()
            
            logger.info(f"Query for conversation_id={conversation.id}, memory_length={chatbot_config.memory_length}")
            logger.info(f"Found {len(messages)} messages in conversation history")
            
            # If we don't have any messages, manually add the user message we just created
            if len(messages) == 0:
                logger.warning(f"No messages found in query, but we just created message {user_message.id}")
                logger.warning(f"Using the user message we just created")
                messages = [user_message]
            
            for idx, msg in enumerate(messages):
                logger.info(f"Message {idx}: id={msg.id}, role={msg.role}, content_preview={msg.content[:50] if msg.content else 'None'}...")
            
            # Generate response
            response_content, sources = await self._generate_response(
                request.message, messages, chatbot_config, request.context, db
            )
            
            # Create assistant message
            assistant_message = DBMessage(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT.value,
                content=response_content,
                sources=sources,
                metadata={"model": chatbot_config.model, "temperature": chatbot_config.temperature}
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)
            
            # Update conversation timestamp
            conversation.updated_at = datetime.utcnow()
            db.commit()
            
            return ChatResponse(
                response=response_content,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                sources=sources
            )
            
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            # Return fallback response
            fallback = chatbot_config.fallback_responses[0] if chatbot_config.fallback_responses else "I'm having trouble responding right now."
            
            assistant_message = DBMessage(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT.value,
                content=fallback,
                metadata={"error": str(e), "fallback": True}
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)
            
            return ChatResponse(
                response=fallback,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                metadata={"error": str(e), "fallback": True}
            )
    
    async def _generate_response(self, message: str, db_messages: List[DBMessage], 
                               config: ChatbotConfig, context: Optional[Dict] = None, db: Session = None) -> tuple[str, Optional[List]]:
        """Generate response using LLM with optional RAG"""
        
        # Lazy load dependencies if not available
        await self._ensure_dependencies()
        
        sources = None
        rag_context = ""
        
        # RAG search if enabled
        if config.use_rag and config.rag_collection and self.rag_module:
            logger.info(f"RAG search enabled for collection: {config.rag_collection}")
            try:
                # Get the Qdrant collection name from RAG collection
                qdrant_collection_name = await self._get_qdrant_collection_name(config.rag_collection, db)
                logger.info(f"Qdrant collection name: {qdrant_collection_name}")
                
                if qdrant_collection_name:
                    logger.info(f"Searching RAG documents: query='{message[:50]}...', max_results={config.rag_top_k}")
                    rag_results = await self.rag_module.search_documents(
                        query=message,
                        max_results=config.rag_top_k,
                        collection_name=qdrant_collection_name
                    )
                    
                    if rag_results:
                        logger.info(f"RAG search found {len(rag_results)} results")
                        sources = [{"title": f"Document {i+1}", "content": result.document.content[:200]} 
                                  for i, result in enumerate(rag_results)]
                        
                        # Build full RAG context from all results
                        rag_context = "\n\nRelevant information from knowledge base:\n" + "\n\n".join([
                            f"[Document {i+1}]:\n{result.document.content}" for i, result in enumerate(rag_results)
                        ])
                        
                        # Detailed RAG logging - ALWAYS log for debugging
                        logger.info("=== COMPREHENSIVE RAG SEARCH RESULTS ===")
                        logger.info(f"Query: '{message}'")
                        logger.info(f"Collection: {qdrant_collection_name}")
                        logger.info(f"Number of results: {len(rag_results)}")
                        for i, result in enumerate(rag_results):
                            logger.info(f"\n--- RAG Result {i+1} ---")
                            logger.info(f"Score: {getattr(result, 'score', 'N/A')}")
                            logger.info(f"Document ID: {getattr(result.document, 'id', 'N/A')}")
                            logger.info(f"Full Content ({len(result.document.content)} chars):")
                            logger.info(f"{result.document.content}")
                            if hasattr(result.document, 'metadata'):
                                logger.info(f"Metadata: {result.document.metadata}")
                        logger.info(f"\n=== RAG CONTEXT BEING ADDED TO PROMPT ({len(rag_context)} chars) ===")
                        logger.info(rag_context)
                        logger.info("=== END RAG SEARCH RESULTS ===")
                    else:
                        logger.warning("RAG search returned no results")
                else:
                    logger.warning(f"RAG collection '{config.rag_collection}' not found in database")
                    
            except Exception as e:
                logger.warning(f"RAG search failed: {e}")
                import traceback
                logger.warning(f"RAG search traceback: {traceback.format_exc()}")
        
        # Build conversation context (includes the current message from db_messages)
        messages = self._build_conversation_messages(db_messages, config, rag_context, context)
        
        # Note: Current user message is already included in db_messages from the query
        logger.info(f"Built conversation context with {len(messages)} messages")
        
        # LLM completion
        logger.info(f"Attempting LLM completion with model: {config.model}")
        logger.info(f"Messages to send: {len(messages)} messages")
        
        # Always log detailed prompts for debugging
        logger.info("=== COMPREHENSIVE LLM REQUEST ===")
        logger.info(f"Model: {config.model}")
        logger.info(f"Temperature: {config.temperature}")
        logger.info(f"Max tokens: {config.max_tokens}")
        logger.info(f"RAG enabled: {config.use_rag}")
        logger.info(f"RAG collection: {config.rag_collection}")
        if config.use_rag and rag_context:
            logger.info(f"RAG context added: {len(rag_context)} characters")
            logger.info(f"RAG sources: {len(sources) if sources else 0} documents")
        logger.info("\n=== COMPLETE MESSAGES SENT TO LLM ===")
        for i, msg in enumerate(messages):
            logger.info(f"\n--- Message {i+1} ---")
            logger.info(f"Role: {msg['role']}")
            logger.info(f"Content ({len(msg['content'])} chars):")
            # Truncate long content for logging (full RAG context can be very long)
            if len(msg['content']) > 500:
                logger.info(f"{msg['content'][:500]}... [truncated, total {len(msg['content'])} chars]")
            else:
                logger.info(msg['content'])
        logger.info("=== END COMPREHENSIVE LLM REQUEST ===")
        
        try:
            logger.info("Calling LLM service create_chat_completion...")
            
            # Convert messages to LLM service format
            llm_messages = [LLMChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]
            
            # Create LLM service request
            llm_request = LLMChatRequest(
                model=config.model,
                messages=llm_messages,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                user_id="chatbot_user",
                api_key_id=0  # Chatbot module uses internal service
            )
            
            # Make request to LLM service
            llm_response = await llm_service.create_chat_completion(llm_request)
            
            # Extract response content
            if llm_response.choices:
                content = llm_response.choices[0].message.content
                logger.info(f"Response content length: {len(content)}")
                
                # Always log response for debugging
                logger.info("=== COMPREHENSIVE LLM RESPONSE ===")
                logger.info(f"Response content ({len(content)} chars):")
                logger.info(content)
                if llm_response.usage:
                    usage = llm_response.usage
                    logger.info(f"Token usage - Prompt: {usage.prompt_tokens}, Completion: {usage.completion_tokens}, Total: {usage.total_tokens}")
                if sources:
                    logger.info(f"RAG sources included: {len(sources)} documents")
                logger.info("=== END COMPREHENSIVE LLM RESPONSE ===")
                
                return content, sources
            else:
                logger.warning("No choices in LLM response")
                return "I received an empty response from the AI model.", sources
                
        except SecurityError as e:
            logger.error(f"Security error in LLM completion: {e}")
            raise HTTPException(status_code=400, detail=f"Security validation failed: {e.message}")
        except ProviderError as e:
            logger.error(f"Provider error in LLM completion: {e}")
            raise HTTPException(status_code=503, detail="LLM service temporarily unavailable")
        except LLMError as e:
            logger.error(f"LLM service error: {e}")
            raise HTTPException(status_code=500, detail="LLM service error")
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            # Return fallback if available
            return "I'm currently unable to process your request. Please try again later.", None
    
    def _build_conversation_messages(self, db_messages: List[DBMessage], config: ChatbotConfig, 
                                   rag_context: str = "", context: Optional[Dict] = None) -> List[Dict]:
        """Build messages array for LLM completion"""
        
        messages = []
        
        # System prompt
        system_prompt = config.system_prompt
        if rag_context:
            # Add explicit instruction to use RAG context
            system_prompt += "\n\nIMPORTANT: Use the following information from the knowledge base to answer the user's question. " \
                           "This information is directly relevant to their query and should be your primary source:\n" + rag_context
        if context and context.get('additional_instructions'):
            system_prompt += f"\n\nAdditional instructions: {context['additional_instructions']}"
            
        messages.append({"role": "system", "content": system_prompt})
        
        logger.info(f"Building messages from {len(db_messages)} database messages")
        
        # Conversation history (messages are already limited by memory_length in the query)
        # Reverse to get chronological order
        # Include ALL messages - the current user message is needed for the LLM to respond!
        for idx, msg in enumerate(reversed(db_messages)):
            logger.info(f"Processing message {idx}: role={msg.role}, content_preview={msg.content[:50] if msg.content else 'None'}...")
            if msg.role in ["user", "assistant"]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
                logger.info(f"Added message with role {msg.role} to LLM messages")
            else:
                logger.info(f"Skipped message with role {msg.role}")
        
        logger.info(f"Final messages array has {len(messages)} messages")  # For debugging, can be removed in production
        return messages
    
    async def _get_or_create_conversation(self, conversation_id: Optional[str], 
                                        chatbot_id: str, user_id: str, db: Session) -> DBConversation:
        """Get existing conversation or create new one"""
        
        if conversation_id:
            conversation = db.query(DBConversation).filter(DBConversation.id == conversation_id).first()
            if conversation:
                return conversation
        
        # Create new conversation
        conversation = DBConversation(
            chatbot_id=chatbot_id,
            user_id=user_id,
            title="New Conversation"
        )
        
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation
    
    def get_router(self) -> APIRouter:
        """Get FastAPI router for chatbot endpoints"""
        router = APIRouter(prefix="/chatbot", tags=["chatbot"])
        
        @router.post("/chat", response_model=ChatResponse)
        async def chat_endpoint(
            request: ChatRequest,
            current_user: User = Depends(get_current_user),
            db: Session = Depends(get_db)
        ):
            """Chat completion endpoint"""
            return await self.chat_completion(request, str(current_user['id']), db)
        
        @router.post("/create", response_model=ChatbotInstance)
        async def create_chatbot_endpoint(
            config: ChatbotConfig,
            current_user: User = Depends(get_current_user),
            db: Session = Depends(get_db)
        ):
            """Create new chatbot instance"""
            return await self.create_chatbot(config, str(current_user['id']), db)
        
        @router.get("/list", response_model=List[ChatbotInstance])
        async def list_chatbots_endpoint(
            current_user: User = Depends(get_current_user),
            db: Session = Depends(get_db)
        ):
            """List user's chatbots"""
            db_chatbots = db.query(DBChatbotInstance).filter(
                (DBChatbotInstance.created_by == str(current_user['id'])) | 
                (DBChatbotInstance.created_by == "system")
            ).all()
            
            chatbots = []
            for db_chatbot in db_chatbots:
                chatbot = ChatbotInstance(
                    id=db_chatbot.id,
                    name=db_chatbot.name,
                    config=ChatbotConfig(**db_chatbot.config),
                    created_by=db_chatbot.created_by,
                    created_at=db_chatbot.created_at,
                    updated_at=db_chatbot.updated_at,
                    is_active=db_chatbot.is_active
                )
                chatbots.append(chatbot)
            
            return chatbots
        
        @router.get("/conversations/{conversation_id}", response_model=Conversation)
        async def get_conversation_endpoint(
            conversation_id: str,
            current_user: User = Depends(get_current_user),
            db: Session = Depends(get_db)
        ):
            """Get conversation history"""
            conversation = db.query(DBConversation).filter(
                DBConversation.id == conversation_id
            ).first()
            
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            # Check if user owns this conversation
            if conversation.user_id != str(current_user['id']):
                raise HTTPException(status_code=403, detail="Not authorized")
            
            # Get messages
            messages = db.query(DBMessage).filter(
                DBMessage.conversation_id == conversation_id
            ).order_by(DBMessage.timestamp).all()
            
            # Convert to response model
            chat_messages = []
            for msg in messages:
                chat_message = ChatMessage(
                    id=msg.id,
                    role=MessageRole(msg.role),
                    content=msg.content,
                    timestamp=msg.timestamp,
                    metadata=msg.metadata or {},
                    sources=msg.sources
                )
                chat_messages.append(chat_message)
            
            response_conversation = Conversation(
                id=conversation.id,
                chatbot_id=conversation.chatbot_id,
                user_id=conversation.user_id,
                messages=chat_messages,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
                metadata=conversation.context_data or {}
            )
            
            return response_conversation
        
        @router.get("/types", response_model=List[Dict[str, str]])
        async def get_chatbot_types_endpoint():
            """Get available chatbot types and their descriptions"""
            return [
                {"type": "assistant", "name": "General Assistant", "description": "Helpful AI assistant for general questions"},
                {"type": "customer_support", "name": "Customer Support", "description": "Professional customer service chatbot"},
                {"type": "teacher", "name": "Teacher", "description": "Educational tutor and learning assistant"},
                {"type": "researcher", "name": "Researcher", "description": "Research assistant with fact-checking focus"},
                {"type": "creative_writer", "name": "Creative Writer", "description": "Creative writing and storytelling assistant"},
                {"type": "custom", "name": "Custom", "description": "Custom chatbot with user-defined personality"}
            ]
        
        return router
    
    # API Compatibility Methods
    async def chat(self, chatbot_config: Dict[str, Any], message: str, 
                   conversation_history: List = None, user_id: str = "anonymous") -> Dict[str, Any]:
        """Chat method for API compatibility"""
        logger.info(f"Chat method called with message: {message[:50]}... by user: {user_id}")
        
        # Lazy load dependencies
        await self._ensure_dependencies()
        
        logger.info(f"LLM service available: {llm_service._initialized}")
        logger.info(f"RAG module available: {self.rag_module is not None}")
        
        try:
            # Create a minimal database session for the chat
            from app.db.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Convert config dict to ChatbotConfig
                config = ChatbotConfig(
                    name=chatbot_config.get("name", "Unknown"),
                    chatbot_type=chatbot_config.get("chatbot_type", "assistant"),
                    model=chatbot_config.get("model", "gpt-3.5-turbo"),
                    system_prompt=chatbot_config.get("system_prompt", ""),
                    temperature=chatbot_config.get("temperature", 0.7),
                    max_tokens=chatbot_config.get("max_tokens", 1000),
                    memory_length=chatbot_config.get("memory_length", 10),
                    use_rag=chatbot_config.get("use_rag", False),
                    rag_collection=chatbot_config.get("rag_collection"),
                    rag_top_k=chatbot_config.get("rag_top_k", 5),
                    fallback_responses=chatbot_config.get("fallback_responses", [])
                )
                
                # Generate response using internal method
                # Create a temporary message object for the current user message
                temp_messages = [
                    DBMessage(
                        id=0,
                        conversation_id=0,
                        role="user",
                        content=message,
                        timestamp=datetime.utcnow(),
                        metadata={}
                    )
                ]

                response_content, sources = await self._generate_response(
                    message, temp_messages, config, None, db
                )
                
                return {
                    "response": response_content,
                    "sources": sources,
                    "conversation_id": None,
                    "message_id": f"msg_{uuid.uuid4()}"
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Chat method failed: {e}")
            fallback_responses = chatbot_config.get("fallback_responses", [
                "I'm sorry, I'm having trouble processing your request right now."
            ])
            return {
                "response": fallback_responses[0] if fallback_responses else "I'm sorry, I couldn't process your request.",
                "sources": None,
                "conversation_id": None,
                "message_id": f"msg_{uuid.uuid4()}"
            }

    # Workflow Integration Methods
    async def workflow_chat_step(self, context: Dict[str, Any], step_config: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Execute chatbot as a workflow step"""
        
        message = step_config.get('message', '')
        chatbot_id = step_config.get('chatbot_id')
        use_rag = step_config.get('use_rag', False)
        
        # Template substitution from context
        message = self._substitute_template_variables(message, context)
        
        request = ChatRequest(
            message=message,
            chatbot_id=chatbot_id,
            use_rag=use_rag,
            context=step_config.get('context', {})
        )
        
        # Use system user for workflow executions
        response = await self.chat_completion(request, "workflow_system", db)
        
        return {
            "response": response.response,
            "conversation_id": response.conversation_id,
            "sources": response.sources,
            "metadata": response.metadata
        }
    
    def _substitute_template_variables(self, template: str, context: Dict[str, Any]) -> str:
        """Simple template variable substitution"""
        import re
        
        def replace_var(match):
            var_path = match.group(1)
            try:
                # Simple dot notation support: context.user.name
                value = context
                for part in var_path.split('.'):
                    value = value[part]
                return str(value)
            except (KeyError, TypeError):
                return match.group(0)  # Return original if not found
        
        return re.sub(r'\\{\\{\\s*([^}]+)\\s*\\}\\}', replace_var, template)
    
    async def _get_qdrant_collection_name(self, collection_identifier: str, db: Session) -> Optional[str]:
        """Get Qdrant collection name from RAG collection ID, name, or direct Qdrant collection"""
        try:
            from app.models.rag_collection import RagCollection
            from sqlalchemy import select
            
            logger.info(f"Looking up RAG collection with identifier: '{collection_identifier}'")
            
            # First check if this might be a direct Qdrant collection name
            # (e.g., starts with "ext_", "rag_", or contains specific patterns)
            if collection_identifier.startswith(("ext_", "rag_", "test_")) or "_" in collection_identifier:
                # Check if this collection exists in Qdrant directly
                actual_collection_name = collection_identifier
                # Remove "ext_" prefix if present
                if collection_identifier.startswith("ext_"):
                    actual_collection_name = collection_identifier[4:]
                
                logger.info(f"Checking if '{actual_collection_name}' exists in Qdrant directly")
                if self.rag_module:
                    try:
                        # Try to verify the collection exists in Qdrant
                        from qdrant_client import QdrantClient
                        qdrant_client = QdrantClient(host="enclava-qdrant", port=6333)
                        collections = qdrant_client.get_collections()
                        collection_names = [c.name for c in collections.collections]
                        
                        if actual_collection_name in collection_names:
                            logger.info(f"Found Qdrant collection directly: {actual_collection_name}")
                            return actual_collection_name
                    except Exception as e:
                        logger.warning(f"Error checking Qdrant collections: {e}")
            
            rag_collection = None
            
            # Then try PostgreSQL lookup by ID if numeric
            if collection_identifier.isdigit():
                logger.info(f"Treating '{collection_identifier}' as collection ID")
                stmt = select(RagCollection).where(
                    RagCollection.id == int(collection_identifier),
                    RagCollection.is_active == True
                )
                result = db.execute(stmt)
                rag_collection = result.scalar_one_or_none()
            
            # If not found by ID, try to look up by name in PostgreSQL
            if not rag_collection:
                logger.info(f"Collection not found by ID, trying by name: '{collection_identifier}'")
                stmt = select(RagCollection).where(
                    RagCollection.name == collection_identifier,
                    RagCollection.is_active == True
                )
                result = db.execute(stmt)
                rag_collection = result.scalar_one_or_none()
            
            if rag_collection:
                logger.info(f"Found RAG collection: ID={rag_collection.id}, name='{rag_collection.name}', qdrant_collection='{rag_collection.qdrant_collection_name}'")
                return rag_collection.qdrant_collection_name
            else:
                logger.warning(f"RAG collection '{collection_identifier}' not found in database (tried both ID and name)")
                return None
                
        except Exception as e:
            logger.error(f"Error looking up RAG collection '{collection_identifier}': {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    # Required abstract methods from BaseModule
    
    async def cleanup(self):
        """Cleanup chatbot module resources"""
        logger.info("Chatbot module cleanup completed")
    
    def get_required_permissions(self) -> List[Permission]:
        """Get required permissions for chatbot module"""
        return [
            Permission("chatbots", "create", "Create chatbot instances"),
            Permission("chatbots", "configure", "Configure chatbot settings"),
            Permission("chatbots", "chat", "Use chatbot for conversations"),
            Permission("chatbots", "manage", "Manage all chatbots")
        ]
    
    async def process_request(self, request_type: str, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process chatbot requests"""
        if request_type == "chat":
            # Handle chat requests
            chat_request = ChatRequest(**data)
            user_id = context.get("user_id", "anonymous")
            db = context.get("db")
            
            if db:
                response = await self.chat_completion(chat_request, user_id, db)
                return {
                    "success": True,
                    "response": response.response,
                    "conversation_id": response.conversation_id,
                    "sources": response.sources
                }
        
        return {"success": False, "error": f"Unknown request type: {request_type}"}


# Module factory function
def create_module(rag_service: Optional[RAGServiceProtocol] = None) -> ChatbotModule:
    """Factory function to create chatbot module instance"""
    return ChatbotModule(rag_service=rag_service)

# Create module instance (dependencies will be injected via factory)
chatbot_module = ChatbotModule()