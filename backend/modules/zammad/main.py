"""
Zammad Integration Module for Enclava Platform

AI-powered ticket summarization using Enclava's chatbot system instead of Ollama.
Provides secure, configurable integration with Zammad ticketing systems.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.services.base_module import BaseModule, Permission, ModuleHealth
from app.core.config import settings
from app.db.database import async_session_factory
from app.models.user import User
from app.models.chatbot import ChatbotInstance
from app.services.llm.service import llm_service
from app.services.llm.models import ChatRequest as LLMChatRequest, ChatMessage as LLMChatMessage
from cryptography.fernet import Fernet
import base64
import os

# Import our module-specific models
from .models import (
    ZammadTicket, 
    ZammadProcessingLog, 
    ZammadConfiguration,
    TicketState,
    ProcessingStatus
)

logger = logging.getLogger(__name__)


class ZammadModule(BaseModule):
    """Zammad Integration Module for AI-powered ticket summarization"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("zammad", config)
        self.name = "Zammad Integration"
        self.description = "AI-powered ticket summarization for Zammad ticketing system"
        self.version = "1.0.0"
        
        # Core services
        self.llm_client = None
        self.session_pool = None
        
        # Processing state
        self.auto_process_task = None
        self.processing_lock = asyncio.Lock()
        
        # Initialize encryption for API tokens
        self._init_encryption()
        
    async def initialize(self) -> None:
        """Initialize the Zammad module"""
        try:
            logger.info("Initializing Zammad module...")
            
            # Initialize LLM service for chatbot integration
            # Note: llm_service is already a global singleton, no need to create instance
            
            # Create HTTP session pool for Zammad API calls
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            self.session_pool = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Enclava-Zammad-Integration/1.0.0"
                }
            )
            
            # Verify database tables exist (they should be created by migration)
            await self._verify_database_tables()
            
            # Start auto-processing if enabled
            await self._start_auto_processing()
            
            self.initialized = True
            self.health.status = "healthy"
            self.health.message = "Zammad module initialized successfully"
            
            logger.info("Zammad module initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Zammad module: {e}")
            self.health.status = "error"
            self.health.message = f"Initialization failed: {str(e)}"
            raise
    
    async def cleanup(self) -> None:
        """Cleanup module resources"""
        try:
            logger.info("Cleaning up Zammad module...")
            
            # Stop auto-processing
            if self.auto_process_task and not self.auto_process_task.done():
                self.auto_process_task.cancel()
                try:
                    await self.auto_process_task
                except asyncio.CancelledError:
                    pass
            
            # Close HTTP session
            if self.session_pool and not self.session_pool.closed:
                await self.session_pool.close()
            
            self.initialized = False
            logger.info("Zammad module cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during Zammad module cleanup: {e}")
    
    def get_required_permissions(self) -> List[Permission]:
        """Return list of permissions this module requires"""
        return [
            Permission("zammad", "read", "Read Zammad tickets and configurations"),
            Permission("zammad", "write", "Create and update Zammad ticket summaries"),
            Permission("zammad", "configure", "Configure Zammad integration settings"),
            Permission("chatbot", "use", "Use chatbot for AI summarization"),
        ]
    
    async def process_request(self, request: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a module request"""
        action = request.get("action", "unknown")
        user_id = context.get("user_id")
        
        logger.info(f"Processing Zammad request: {action} for user {user_id}")
        
        # Route to appropriate handler based on action
        if action == "process_tickets":
            return await self._handle_process_tickets(request, context)
        elif action == "get_ticket_summary":
            return await self._handle_get_ticket_summary(request, context)
        elif action == "process_single_ticket":
            return await self._handle_process_single_ticket(request, context)
        elif action == "get_status":
            return await self._handle_get_status(request, context)
        elif action == "get_configurations":
            return await self._handle_get_configurations(request, context)
        elif action == "save_configuration":
            return await self._handle_save_configuration(request, context)
        elif action == "test_connection":
            return await self._handle_test_connection(request, context)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _handle_process_tickets(self, request: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle batch ticket processing request"""
        async with self.processing_lock:
            user_id = context.get("user_id")
            config_id = request.get("config_id")
            filters = request.get("filters", {})
            
            # Get user configuration
            config = await self._get_user_configuration(user_id, config_id)
            if not config:
                raise ValueError("Configuration not found")
            
            # Create processing batch
            batch_id = str(uuid.uuid4())
            
            # Start processing
            result = await self._process_tickets_batch(
                config=config,
                batch_id=batch_id,
                user_id=user_id,
                filters=filters
            )
            
            return {
                "batch_id": batch_id,
                "status": "completed",
                "result": result
            }
    
    async def _handle_get_ticket_summary(self, request: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get ticket summary request"""
        ticket_id = request.get("ticket_id")
        if not ticket_id:
            raise ValueError("ticket_id is required")
        
        async with async_session_factory() as db:
            # Get ticket from database
            stmt = select(ZammadTicket).where(ZammadTicket.zammad_ticket_id == ticket_id)
            result = await db.execute(stmt)
            ticket = result.scalar_one_or_none()
            
            if not ticket:
                return {"error": "Ticket not found", "ticket_id": ticket_id}
            
            return {"ticket": ticket.to_dict()}
    
    async def _handle_process_single_ticket(self, request: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle single ticket processing request"""
        user_id = context.get("user_id")
        ticket_id = request.get("ticket_id")
        config_id = request.get("config_id")
        
        if not ticket_id:
            raise ValueError("ticket_id is required")
        
        # Get user configuration
        config = await self._get_user_configuration(user_id, config_id)
        if not config:
            raise ValueError("Configuration not found")
        
        # Process single ticket
        result = await self._process_single_ticket(config, ticket_id, user_id)
        
        return {"ticket_id": ticket_id, "result": result}
    
    async def _handle_get_status(self, request: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get module status request"""
        user_id = context.get("user_id")
        
        async with async_session_factory() as db:
            # Import func for count queries
            from sqlalchemy import func
            
            # Get processing statistics - use func.count() to get actual counts
            total_tickets_result = await db.scalar(
                select(func.count(ZammadTicket.id)).where(ZammadTicket.processed_by_user_id == user_id)
            )
            total_tickets = total_tickets_result or 0
            
            processed_tickets_result = await db.scalar(
                select(func.count(ZammadTicket.id)).where(
                    and_(
                        ZammadTicket.processed_by_user_id == user_id,
                        ZammadTicket.processing_status == ProcessingStatus.COMPLETED.value
                    )
                )
            )
            processed_tickets = processed_tickets_result or 0
            
            failed_tickets_result = await db.scalar(
                select(func.count(ZammadTicket.id)).where(
                    and_(
                        ZammadTicket.processed_by_user_id == user_id,
                        ZammadTicket.processing_status == ProcessingStatus.FAILED.value
                    )
                )
            )
            failed_tickets = failed_tickets_result or 0
            
            # Get recent processing logs
            recent_logs = await db.execute(
                select(ZammadProcessingLog)
                .where(ZammadProcessingLog.initiated_by_user_id == user_id)
                .order_by(ZammadProcessingLog.started_at.desc())
                .limit(10)
            )
            logs = [log.to_dict() for log in recent_logs.scalars()]
            
            return {
                "module_health": self.get_health().__dict__,
                "module_metrics": self.get_metrics().__dict__,
                "statistics": {
                    "total_tickets": total_tickets,
                    "processed_tickets": processed_tickets,
                    "failed_tickets": failed_tickets,
                    "success_rate": (processed_tickets / max(total_tickets, 1)) * 100 if total_tickets > 0 else 0
                },
                "recent_processing_logs": logs
            }
    
    async def _handle_get_configurations(self, request: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get configurations request"""
        user_id = context.get("user_id")
        
        async with async_session_factory() as db:
            stmt = (
                select(ZammadConfiguration)
                .where(ZammadConfiguration.user_id == user_id)
                .where(ZammadConfiguration.is_active == True)
                .order_by(ZammadConfiguration.is_default.desc(), ZammadConfiguration.created_at.desc())
            )
            result = await db.execute(stmt)
            configs = [config.to_dict() for config in result.scalars()]
            
            return {"configurations": configs}
    
    async def _handle_save_configuration(self, request: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle save configuration request"""
        user_id = context.get("user_id")
        config_data = request.get("configuration", {})
        
        # Validate required fields
        required_fields = ["name", "zammad_url", "api_token", "chatbot_id"]
        for field in required_fields:
            if not config_data.get(field):
                raise ValueError(f"Required field missing: {field}")
        
        async with async_session_factory() as db:
            # Verify chatbot exists and user has access
            chatbot_stmt = select(ChatbotInstance).where(
                and_(
                    ChatbotInstance.id == config_data["chatbot_id"],
                    ChatbotInstance.created_by == str(user_id),
                    ChatbotInstance.is_active == True
                )
            )
            chatbot = await db.scalar(chatbot_stmt)
            if not chatbot:
                raise ValueError("Chatbot not found or access denied")
            
            # Encrypt API token
            encrypted_token = self._encrypt_data(config_data["api_token"])
            
            # Create new configuration
            config = ZammadConfiguration(
                user_id=user_id,
                name=config_data["name"],
                description=config_data.get("description"),
                is_default=config_data.get("is_default", False),
                zammad_url=config_data["zammad_url"].rstrip("/"),
                api_token_encrypted=encrypted_token,
                chatbot_id=config_data["chatbot_id"],
                process_state=config_data.get("process_state", "open"),
                max_tickets=config_data.get("max_tickets", 10),
                skip_existing=config_data.get("skip_existing", True),
                auto_process=config_data.get("auto_process", False),
                process_interval=config_data.get("process_interval", 30),
                summary_template=config_data.get("summary_template"),
                custom_settings=config_data.get("custom_settings", {})
            )
            
            # If this is set as default, unset other defaults
            if config.is_default:
                await db.execute(
                    ZammadConfiguration.__table__.update()
                    .where(ZammadConfiguration.user_id == user_id)
                    .values(is_default=False)
                )
            
            db.add(config)
            await db.commit()
            await db.refresh(config)
            
            return {"configuration": config.to_dict()}
    
    async def _handle_test_connection(self, request: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle test Zammad connection request"""
        zammad_url = request.get("zammad_url")
        api_token = request.get("api_token")
        
        if not zammad_url or not api_token:
            raise ValueError("zammad_url and api_token are required")
        
        result = await self._test_zammad_connection(zammad_url, api_token)
        return result
    
    async def _process_tickets_batch(self, config: ZammadConfiguration, batch_id: str, user_id: int, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Process a batch of tickets"""
        async with async_session_factory() as db:
            # Create processing log
            log = ZammadProcessingLog(
                batch_id=batch_id,
                initiated_by_user_id=user_id,
                config_used=config.to_dict(),
                filters_applied=filters,
                status="running"
            )
            db.add(log)
            await db.commit()
            
            start_time = datetime.now(timezone.utc)  # Keep as timezone-aware for calculations
            
            try:
                # Get tickets from Zammad
                tickets = await self._fetch_zammad_tickets(config, filters)
                log.tickets_found = len(tickets)
                
                logger.info(f"Fetched {len(tickets)} tickets from Zammad for processing")
                
                # Process each ticket
                processed = 0
                failed = 0
                skipped = 0
                
                for i, ticket_data in enumerate(tickets, 1):
                    try:
                        # Validate ticket data structure
                        if not isinstance(ticket_data, dict):
                            logger.error(f"Ticket {i} is not a dictionary: {type(ticket_data)}")
                            failed += 1
                            continue
                            
                        ticket_id = ticket_data.get('id', f'unknown-{i}')
                        logger.info(f"Processing ticket {i}/{len(tickets)}: ID {ticket_id}")
                        logger.info(f"Ticket {i} data type: {type(ticket_data)}")
                        logger.info(f"Ticket {i} content: {str(ticket_data)[:300]}...")
                        
                        result = await self._process_ticket_data(config, ticket_data, user_id)
                        
                        if result["status"] == "processed":
                            processed += 1
                        elif result["status"] == "skipped":
                            skipped += 1
                        else:
                            failed += 1
                            
                    except Exception as e:
                        # Safely get ticket ID for error reporting
                        ticket_id = ticket_data.get('id', f'unknown-{i}') if isinstance(ticket_data, dict) else f'unknown-{i}'
                        logger.error(f"Error processing ticket {ticket_id}: {e}")
                        logger.debug(f"Ticket data type: {type(ticket_data)}, content: {str(ticket_data)[:200]}...")
                        failed += 1
                
                # Update log
                end_time = datetime.now(timezone.utc)
                processing_time = (end_time - start_time).total_seconds()
                
                log.completed_at = self._to_naive_utc(end_time)
                log.tickets_processed = processed
                log.tickets_failed = failed
                log.tickets_skipped = skipped
                log.processing_time_seconds = int(processing_time)
                log.average_time_per_ticket = int((processing_time / max(len(tickets), 1)) * 1000)
                log.status = "completed"
                
                await db.commit()
                
                return {
                    "tickets_found": len(tickets),
                    "tickets_processed": processed,
                    "tickets_failed": failed,
                    "tickets_skipped": skipped,
                    "processing_time_seconds": int(processing_time)
                }
                
            except Exception as e:
                # Update log with error
                log.status = "failed"
                log.errors_encountered = [str(e)]
                log.completed_at = self._to_naive_utc(datetime.now(timezone.utc))
                await db.commit()
                raise
    
    async def _process_single_ticket(self, config: ZammadConfiguration, ticket_id: int, user_id: int) -> Dict[str, Any]:
        """Process a single ticket"""
        # Fetch ticket details from Zammad
        ticket_data = await self._fetch_single_zammad_ticket(config, ticket_id)
        if not ticket_data:
            return {"status": "error", "message": "Ticket not found"}
        
        # Process the ticket
        result = await self._process_ticket_data(config, ticket_data, user_id)
        return result
    
    async def _process_ticket_data(self, config: ZammadConfiguration, ticket_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Process individual ticket data"""
        logger.info(f"Processing ticket data: type={type(ticket_data)}, keys={list(ticket_data.keys()) if isinstance(ticket_data, dict) else 'N/A'}")
        
        # Ensure ticket_data is a dictionary
        if not isinstance(ticket_data, dict):
            raise ValueError(f"Expected ticket_data to be a dictionary, got {type(ticket_data)}")
            
        ticket_id = ticket_data.get("id")
        if ticket_id is None:
            raise ValueError("Ticket data missing 'id' field")
            
        # Debug nested field types that might be causing issues
        logger.info(f"Ticket {ticket_id} customer field type: {type(ticket_data.get('customer'))}")
        logger.info(f"Ticket {ticket_id} customer value: {ticket_data.get('customer')}")
        logger.info(f"Ticket {ticket_id} group field type: {type(ticket_data.get('group'))}")
        logger.info(f"Ticket {ticket_id} state field type: {type(ticket_data.get('state'))}")
        logger.info(f"Ticket {ticket_id} priority field type: {type(ticket_data.get('priority'))}")
        
        async with async_session_factory() as db:
            # Check if ticket already exists and should be skipped
            existing = await db.scalar(
                select(ZammadTicket).where(ZammadTicket.zammad_ticket_id == ticket_id)
            )
            
            if existing and config.skip_existing and existing.processing_status == ProcessingStatus.COMPLETED.value:
                return {"status": "skipped", "reason": "already_processed"}
            
            try:
                # Fetch full ticket details and conversation
                logger.info(f"Ticket {ticket_id}: Fetching full ticket details with articles...")
                try:
                    full_ticket = await self._fetch_ticket_with_articles(config, ticket_id)
                    if not full_ticket:
                        return {"status": "error", "message": "Could not fetch ticket details"}
                    logger.info(f"Ticket {ticket_id}: Successfully fetched full ticket details")
                except Exception as e:
                    logger.error(f"Ticket {ticket_id}: Error fetching full ticket details: {e}")
                    raise
                
                # Generate summary using chatbot
                logger.info(f"Ticket {ticket_id}: Generating AI summary...")
                try:
                    summary = await self._generate_ticket_summary(config, full_ticket)
                    logger.info(f"Ticket {ticket_id}: Successfully generated AI summary")
                except Exception as e:
                    logger.error(f"Ticket {ticket_id}: Error generating summary: {e}")
                    raise
                
                # Create/update ticket record
                if existing:
                    ticket_record = existing
                    ticket_record.processing_status = ProcessingStatus.PROCESSING.value
                else:
                    ticket_record = ZammadTicket(
                        zammad_ticket_id=ticket_id,
                        ticket_number=ticket_data.get("number"),
                        title=ticket_data.get("title"),
                        state=ticket_data.get("state"),
                        priority=ticket_data.get("priority"),
                        customer_email=self._safe_get_customer_email(ticket_data),
                        processing_status=ProcessingStatus.PROCESSING.value,
                        processed_by_user_id=user_id,
                        chatbot_id=config.chatbot_id
                    )
                    db.add(ticket_record)
                
                # Update with summary and processing info
                ticket_record.summary = summary
                ticket_record.context_data = full_ticket
                ticket_record.processed_at = self._to_naive_utc(datetime.now(timezone.utc))
                ticket_record.processing_status = ProcessingStatus.COMPLETED.value
                ticket_record.config_snapshot = config.to_dict()
                
                # Safely parse Zammad timestamps and convert to naive UTC for DB
                if ticket_data.get("created_at"):
                    parsed_dt = self._safe_parse_datetime(ticket_data["created_at"])
                    ticket_record.zammad_created_at = self._to_naive_utc(parsed_dt)
                if ticket_data.get("updated_at"):
                    parsed_dt = self._safe_parse_datetime(ticket_data["updated_at"])
                    ticket_record.zammad_updated_at = self._to_naive_utc(parsed_dt)
                
                ticket_record.zammad_article_count = len(full_ticket.get("articles", []))
                
                await db.commit()
                
                # Post summary to Zammad as internal note
                await self._post_summary_to_zammad(config, ticket_id, summary)
                
                return {"status": "processed", "summary": summary}
                
            except Exception as e:
                logger.error(f"Error processing ticket {ticket_id}: {e}")
                
                # Update record with error
                if existing:
                    ticket_record = existing
                else:
                    ticket_record = ZammadTicket(
                        zammad_ticket_id=ticket_id,
                        ticket_number=ticket_data.get("number"),
                        title=ticket_data.get("title"),
                        state=ticket_data.get("state"),
                        processing_status=ProcessingStatus.FAILED.value,
                        processed_by_user_id=user_id,
                        chatbot_id=config.chatbot_id
                    )
                    db.add(ticket_record)
                
                ticket_record.processing_status = ProcessingStatus.FAILED.value
                ticket_record.error_message = str(e)
                ticket_record.processed_at = self._to_naive_utc(datetime.now(timezone.utc))
                
                await db.commit()
                
                return {"status": "error", "message": str(e)}
    
    async def _generate_ticket_summary(self, config: ZammadConfiguration, ticket_data: Dict[str, Any]) -> str:
        """Generate AI summary for ticket using Enclava chatbot"""
        # Build context for the LLM
        context = self._build_ticket_context(ticket_data)
        
        # Get summary template
        template = config.summary_template or (
            "Generate a concise summary of this support ticket including key issues, "
            "customer concerns, and any actions taken."
        )
        
        # Prepare messages for chatbot
        messages = [
            {
                "role": "system",
                "content": f"{template}\n\nPlease provide a professional summary that would be helpful for support agents."
            },
            {
                "role": "user", 
                "content": context
            }
        ]
        
        # Generate summary using new LLM service
        chat_request = LLMChatRequest(
            model=await self._get_chatbot_model(config.chatbot_id),
            messages=[LLMChatMessage(role=msg["role"], content=msg["content"]) for msg in messages],
            temperature=0.3,
            max_tokens=500,
            user_id=str(config.user_id),
            api_key_id=0  # Using 0 for module requests
        )
        
        response = await llm_service.create_chat_completion(chat_request)
        
        # Extract content from new LLM service response
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content.strip()
        
        return "Unable to generate summary."
    
    def _build_ticket_context(self, ticket_data: Dict[str, Any]) -> str:
        """Build formatted context string for AI processing"""
        context_parts = []
        
        # Basic ticket information
        context_parts.append(f"Ticket #{ticket_data.get('number', 'Unknown')}")
        context_parts.append(f"Title: {ticket_data.get('title', 'No title')}")
        context_parts.append(f"State: {ticket_data.get('state', 'Unknown')}")
        
        if ticket_data.get('priority'):
            context_parts.append(f"Priority: {ticket_data['priority']}")
        
        customer_email = self._safe_get_customer_email(ticket_data)
        if customer_email:
            context_parts.append(f"Customer: {customer_email}")
        
        # Add conversation history
        articles = ticket_data.get('articles', [])
        if articles:
            context_parts.append("\nConversation History:")
            
            for i, article in enumerate(articles[-10:], 1):  # Last 10 articles
                try:
                    # Safely extract article data
                    if not isinstance(article, dict):
                        logger.warning(f"Article {i} is not a dictionary: {type(article)}")
                        continue
                        
                    sender = article.get('from', 'Unknown')
                    content = article.get('body', '').strip()
                    
                    if content:
                        # Clean up HTML if present
                        if '<' in content and '>' in content:
                            import re
                            content = re.sub(r'<[^>]+>', '', content)
                            content = content.replace('&nbsp;', ' ')
                            content = content.replace('&amp;', '&')
                            content = content.replace('&lt;', '<')
                            content = content.replace('&gt;', '>')
                        
                        # Truncate very long messages
                        if len(content) > 1000:
                            content = content[:1000] + "... [truncated]"
                        
                        context_parts.append(f"\n{i}. From: {sender}")
                        context_parts.append(f"   {content}")
                        
                except Exception as e:
                    logger.warning(f"Error processing article {i}: {e}")
                    continue
        
        return "\n".join(context_parts)
    
    async def _get_chatbot_model(self, chatbot_id: str) -> str:
        """Get the model name for the specified chatbot"""
        async with async_session_factory() as db:
            chatbot = await db.scalar(
                select(ChatbotInstance).where(ChatbotInstance.id == chatbot_id)
            )
            
            if not chatbot:
                raise ValueError(f"Chatbot {chatbot_id} not found")
            
            # Default to a reasonable model if not specified
            return getattr(chatbot, 'model', 'privatemode-llama-3-70b')
    
    async def _fetch_zammad_tickets(self, config: ZammadConfiguration, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch tickets from Zammad API"""
        # Decrypt API token
        api_token = self._decrypt_data(config.api_token_encrypted)
        
        url = urljoin(config.zammad_url, "/api/v1/tickets")
        headers = {
            "Authorization": f"Token token={api_token}",
            "Content-Type": "application/json"
        }
        
        # Build query parameters
        params = {
            "expand": "true",
            "per_page": filters.get("limit", config.max_tickets)
        }
        
        # Add state filter
        state = filters.get("state", config.process_state)
        if state and state != "all":
            params["state"] = state
        
        async with self.session_pool.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                
                # Handle different Zammad API response formats
                if isinstance(data, list):
                    # Zammad returned a list directly
                    tickets = data
                    logger.info(f"Zammad API returned list directly with {len(tickets)} tickets")
                elif isinstance(data, dict):
                    # Zammad returned a dictionary with "tickets" key
                    tickets = data.get("tickets", [])
                    logger.info(f"Zammad API returned dict with {len(tickets)} tickets")
                    logger.debug(f"Zammad API response structure: keys={list(data.keys())}")
                else:
                    logger.error(f"Unexpected Zammad API response type: {type(data)}")
                    raise Exception(f"Zammad API returned unexpected data type: {type(data)}")
                
                # Validate that tickets is actually a list
                if not isinstance(tickets, list):
                    logger.error(f"Expected tickets to be a list, got {type(tickets)}: {str(tickets)[:200]}...")
                    raise Exception(f"Zammad API returned invalid ticket data structure: expected list, got {type(tickets)}")
                
                return tickets
            else:
                error_text = await response.text()
                raise Exception(f"Zammad API error {response.status}: {error_text}")
    
    async def _fetch_single_zammad_ticket(self, config: ZammadConfiguration, ticket_id: int) -> Optional[Dict[str, Any]]:
        """Fetch single ticket from Zammad API"""
        api_token = self._decrypt_data(config.api_token_encrypted)
        
        url = urljoin(config.zammad_url, f"/api/v1/tickets/{ticket_id}")
        headers = {
            "Authorization": f"Token token={api_token}",
            "Content-Type": "application/json"
        }
        
        params = {"expand": "true"}
        
        async with self.session_pool.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 404:
                return None
            else:
                error_text = await response.text()
                raise Exception(f"Zammad API error {response.status}: {error_text}")
    
    async def _fetch_ticket_with_articles(self, config: ZammadConfiguration, ticket_id: int) -> Optional[Dict[str, Any]]:
        """Fetch ticket with full conversation articles"""
        # Get basic ticket info
        ticket = await self._fetch_single_zammad_ticket(config, ticket_id)
        if not ticket:
            return None
        
        # Fetch articles
        api_token = self._decrypt_data(config.api_token_encrypted)
        articles_url = urljoin(config.zammad_url, f"/api/v1/ticket_articles/by_ticket/{ticket_id}")
        headers = {
            "Authorization": f"Token token={api_token}",
            "Content-Type": "application/json"
        }
        
        async with self.session_pool.get(articles_url, headers=headers) as response:
            if response.status == 200:
                articles_data = await response.json()
                
                # Handle different Zammad articles API response formats
                if isinstance(articles_data, list):
                    # Articles returned as list directly
                    articles = articles_data
                    logger.info(f"Articles API returned list directly with {len(articles)} articles for ticket {ticket_id}")
                elif isinstance(articles_data, dict):
                    # Articles returned as dictionary with "articles" key
                    articles = articles_data.get("articles", [])
                    logger.info(f"Articles API returned dict with {len(articles)} articles for ticket {ticket_id}")
                else:
                    logger.error(f"Unexpected articles API response type for ticket {ticket_id}: {type(articles_data)}")
                    articles = []
                
                ticket["articles"] = articles
            else:
                logger.warning(f"Could not fetch articles for ticket {ticket_id}: {response.status}")
                ticket["articles"] = []
        
        return ticket
    
    async def _post_summary_to_zammad(self, config: ZammadConfiguration, ticket_id: int, summary: str) -> bool:
        """Post AI summary as internal note to Zammad ticket"""
        try:
            api_token = self._decrypt_data(config.api_token_encrypted)
            
            url = urljoin(config.zammad_url, "/api/v1/ticket_articles")
            headers = {
                "Authorization": f"Token token={api_token}",
                "Content-Type": "application/json"
            }
            
            # Create internal note payload
            article_data = {
                "ticket_id": ticket_id,
                "type": "note",
                "internal": True,  # This ensures only agents can see it
                "subject": "AI Summary - Enclava",
                "body": f"**AI-Generated Summary**\n\n{summary}\n\n---\n*Generated by Enclava AI at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC*"
            }
            
            async with self.session_pool.post(url, headers=headers, json=article_data) as response:
                if response.status in (200, 201):
                    logger.info(f"Successfully posted AI summary to ticket {ticket_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to post summary to ticket {ticket_id}: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error posting summary to Zammad ticket {ticket_id}: {e}")
            return False
    
    async def _test_zammad_connection(self, zammad_url: str, api_token: str) -> Dict[str, Any]:
        """Test connection to Zammad instance"""
        try:
            url = urljoin(zammad_url.rstrip("/"), "/api/v1/users/me")
            headers = {
                "Authorization": f"Token token={api_token}",
                "Content-Type": "application/json"
            }
            
            async with self.session_pool.get(url, headers=headers) as response:
                if response.status == 200:
                    user_data = await response.json()
                    return {
                        "status": "success",
                        "message": "Connection successful",
                        "user": user_data.get("email", "Unknown"),
                        "zammad_version": response.headers.get("X-Zammad-Version", "Unknown")
                    }
                else:
                    error_text = await response.text()
                    return {
                        "status": "error",
                        "message": f"Connection failed: HTTP {response.status}",
                        "details": error_text
                    }
                    
        except Exception as e:
            return {
                "status": "error",
                "message": f"Connection error: {str(e)}"
            }
    
    async def _get_user_configuration(self, user_id: int, config_id: Optional[int] = None) -> Optional[ZammadConfiguration]:
        """Get user configuration by ID or default"""
        async with async_session_factory() as db:
            if config_id:
                stmt = select(ZammadConfiguration).where(
                    and_(
                        ZammadConfiguration.id == config_id,
                        ZammadConfiguration.user_id == user_id,
                        ZammadConfiguration.is_active == True
                    )
                )
            else:
                # Get default configuration
                stmt = select(ZammadConfiguration).where(
                    and_(
                        ZammadConfiguration.user_id == user_id,
                        ZammadConfiguration.is_active == True,
                        ZammadConfiguration.is_default == True
                    )
                ).order_by(ZammadConfiguration.created_at.desc())
            
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
    
    async def _verify_database_tables(self):
        """Verify that required database tables exist"""
        # This would be handled by Alembic migrations in production
        # For now, just log that we expect the tables to exist
        logger.info("Verifying database tables for Zammad module")
        
    async def _start_auto_processing(self):
        """Start auto-processing task if any configurations have it enabled"""
        # This would start a background task to periodically check for auto-process configs
        # and process new tickets automatically
        logger.info("Auto-processing monitoring not implemented yet")
        pass
    
    def _init_encryption(self):
        """Initialize encryption for API tokens"""
        # Use a fixed key for demo - in production, this should be from environment
        key = os.environ.get('ZAMMAD_ENCRYPTION_KEY', 'demo-key-for-zammad-tokens-12345678901234567890123456789012')
        # Ensure key is exactly 32 bytes for Fernet
        key = key.encode()[:32].ljust(32, b'0')
        self.encryption_key = base64.urlsafe_b64encode(key)
        self.cipher = Fernet(self.encryption_key)
    
    def _encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def _safe_get_customer_email(self, ticket_data: Dict[str, Any]) -> Optional[str]:
        """Safely extract customer email from ticket data"""
        try:
            customer = ticket_data.get('customer')
            if not customer:
                return None
                
            # Handle case where customer is a dictionary
            if isinstance(customer, dict):
                return customer.get('email')
                
            # Handle case where customer is a list (sometimes Zammad returns a list)
            elif isinstance(customer, list) and len(customer) > 0:
                first_customer = customer[0]
                if isinstance(first_customer, dict):
                    return first_customer.get('email')
                    
            # Handle case where customer is just the email string
            elif isinstance(customer, str) and '@' in customer:
                return customer
                
            return None
            
        except Exception as e:
            logger.warning(f"Could not extract customer email from ticket data: {e}")
            return None
    
    def _safe_parse_datetime(self, datetime_str: str) -> Optional[datetime]:
        """Safely parse datetime string from Zammad API to timezone-aware datetime"""
        if not datetime_str:
            return None
            
        try:
            # Handle different Zammad datetime formats
            if datetime_str.endswith('Z'):
                # ISO format with Z suffix: "2025-08-20T12:07:28.857000Z"
                return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            elif '+' in datetime_str or '-' in datetime_str[-6:]:
                # Already has timezone info: "2025-08-20T12:07:28.857000+00:00"
                return datetime.fromisoformat(datetime_str)
            else:
                # No timezone info - assume UTC: "2025-08-20T12:07:28.857000"
                dt = datetime.fromisoformat(datetime_str)
                if dt.tzinfo is None:
                    # Make it timezone-aware as UTC
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
                
        except Exception as e:
            logger.warning(f"Could not parse datetime '{datetime_str}': {e}")
            return None
    
    def _to_naive_utc(self, dt: datetime) -> datetime:
        """Convert timezone-aware datetime to naive UTC for database storage"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # Already naive, assume it's UTC
            return dt
        # Convert to UTC and make naive
        return dt.astimezone(timezone.utc).replace(tzinfo=None)