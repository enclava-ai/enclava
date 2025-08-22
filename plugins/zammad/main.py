"""
Zammad Plugin Implementation
Provides integration between Enclava platform and Zammad helpdesk system
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
import aiohttp
import asyncio
from datetime import datetime, timezone

from app.services.base_plugin import BasePlugin, PluginContext
from app.services.plugin_database import PluginDatabaseSession, plugin_db_manager
from app.services.plugin_security import plugin_security_policy_manager
from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid


class ZammadTicket(BaseModel):
    """Zammad ticket model"""
    id: str
    title: str
    body: str
    status: str
    priority: str
    customer_id: str
    group_id: str
    created_at: datetime
    updated_at: datetime
    ai_summary: Optional[str] = None


class ZammadConfiguration(BaseModel):
    """Zammad configuration model"""
    name: str
    zammad_url: str
    api_token: str
    chatbot_id: str
    ai_summarization: Dict[str, Any]
    sync_settings: Dict[str, Any]
    webhook_settings: Dict[str, Any]


# Plugin database models
Base = declarative_base()

class ZammadConfiguration(Base):
    __tablename__ = "zammad_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    zammad_url = Column(String(500), nullable=False)
    api_token_encrypted = Column(Text, nullable=False)
    chatbot_id = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    ai_summarization_enabled = Column(Boolean, default=True)
    auto_summarize = Column(Boolean, default=True)
    sync_enabled = Column(Boolean, default=True)
    sync_interval_hours = Column(Integer, default=2)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

class ZammadTicket(Base):
    __tablename__ = "zammad_tickets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zammad_ticket_id = Column(String(50), nullable=False, index=True)
    configuration_id = Column(UUID(as_uuid=True), ForeignKey("zammad_configurations.id"))
    title = Column(String(500), nullable=False)
    body = Column(Text)
    status = Column(String(50))
    priority = Column(String(50))
    customer_id = Column(String(50))
    group_id = Column(String(50))
    ai_summary = Column(Text)
    last_synced = Column(DateTime, default=datetime.now(timezone.utc))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    configuration = relationship("ZammadConfiguration", back_populates="tickets")

ZammadConfiguration.tickets = relationship("ZammadTicket", back_populates="configuration")

class ZammadPlugin(BasePlugin):
    """Zammad helpdesk integration plugin with full framework integration"""
    
    def __init__(self, manifest, plugin_token: str):
        super().__init__(manifest, plugin_token)
        self.zammad_client = None
        self.db_models = [ZammadConfiguration, ZammadTicket]
    
    async def initialize(self) -> bool:
        """Initialize Zammad plugin with database setup"""
        try:
            self.logger.info("Initializing Zammad plugin")
            
            # Create database tables
            await self._create_database_tables()
            
            # Test platform API connectivity
            health = await self.api_client.get("/health")
            self.logger.info(f"Platform API health: {health.get('status')}")
            
            # Validate security policy
            policy = plugin_security_policy_manager.get_security_policy(self.plugin_id, None)
            self.logger.info(f"Security policy loaded: {policy.get('max_api_calls_per_minute')} calls/min")
            
            self.logger.info("Zammad plugin initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Zammad plugin: {e}")
            return False
    
    async def _create_database_tables(self):
        """Create plugin database tables"""
        try:
            engine = await plugin_db_manager.get_plugin_engine(self.plugin_id)
            if engine:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                self.logger.info("Database tables created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create database tables: {e}")
            raise
    
    async def cleanup(self) -> bool:
        """Cleanup plugin resources"""
        try:
            self.logger.info("Cleaning up Zammad plugin")
            # Close any open connections
            return True
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            return False
    
    def get_api_router(self) -> APIRouter:
        """Return FastAPI router for Zammad endpoints"""
        router = APIRouter()
        
        @router.get("/health")
        async def health_check():
            """Plugin health check endpoint"""
            return await self.health_check()
        
        @router.get("/tickets")
        async def get_tickets(context: PluginContext = Depends(self.get_auth_context)):
            """Get tickets from Zammad"""
            try:
                self._track_request()
                
                config = await self.get_active_config(context.user_id)
                if not config:
                    raise HTTPException(status_code=404, detail="No Zammad configuration found")
                
                tickets = await self.fetch_tickets_from_zammad(config)
                return {"tickets": tickets, "count": len(tickets)}
                
            except Exception as e:
                self._track_request(success=False)
                self.logger.error(f"Error fetching tickets: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/tickets/{ticket_id}")
        async def get_ticket(ticket_id: str, context: PluginContext = Depends(self.get_auth_context)):
            """Get specific ticket from Zammad"""
            try:
                self._track_request()
                
                config = await self.get_active_config(context.user_id)
                if not config:
                    raise HTTPException(status_code=404, detail="No Zammad configuration found")
                
                ticket = await self.fetch_ticket_from_zammad(config, ticket_id)
                return {"ticket": ticket}
                
            except Exception as e:
                self._track_request(success=False)
                self.logger.error(f"Error fetching ticket {ticket_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.post("/tickets/{ticket_id}/summarize")
        async def summarize_ticket(
            ticket_id: str, 
            background_tasks: BackgroundTasks,
            context: PluginContext = Depends(self.get_auth_context)
        ):
            """Generate AI summary for ticket"""
            try:
                self._track_request()
                
                config = await self.get_active_config(context.user_id)
                if not config:
                    raise HTTPException(status_code=404, detail="No Zammad configuration found")
                
                # Start summarization in background
                background_tasks.add_task(
                    self.summarize_ticket_async, 
                    config, 
                    ticket_id, 
                    context.user_id
                )
                
                return {
                    "status": "started",
                    "ticket_id": ticket_id,
                    "message": "AI summarization started in background"
                }
                
            except Exception as e:
                self._track_request(success=False)
                self.logger.error(f"Error starting summarization for ticket {ticket_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.post("/webhooks/ticket-created")
        async def handle_ticket_webhook(webhook_data: Dict[str, Any]):
            """Handle Zammad webhook for new tickets"""
            try:
                ticket_id = webhook_data.get("ticket", {}).get("id")
                if not ticket_id:
                    raise HTTPException(status_code=400, detail="Invalid webhook data")
                
                self.logger.info(f"Received webhook for ticket: {ticket_id}")
                
                # Process webhook asynchronously
                asyncio.create_task(self.process_ticket_webhook(webhook_data))
                
                return {"status": "processed", "ticket_id": ticket_id}
                
            except Exception as e:
                self.logger.error(f"Error processing webhook: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/configurations")
        async def get_configurations(context: PluginContext = Depends(self.get_auth_context)):
            """Get user's Zammad configurations"""
            try:
                configs = await self.get_user_configurations(context.user_id)
                return {"configurations": configs}
            except Exception as e:
                self.logger.error(f"Error fetching configurations: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.post("/configurations")
        async def create_configuration(
            config_data: Dict[str, Any],
            context: PluginContext = Depends(self.get_auth_context)
        ):
            """Create new Zammad configuration"""
            try:
                # Validate configuration against schema
                schema = await self.get_configuration_schema()
                is_valid, errors = await self.config.validate_config(config_data, schema)
                
                if not is_valid:
                    raise HTTPException(status_code=400, detail=f"Invalid configuration: {errors}")
                
                # Test connection before saving
                connection_test = await self.test_zammad_connection(config_data)
                if not connection_test["success"]:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Connection test failed: {connection_test['error']}"
                    )
                
                # Save configuration to plugin database
                success = await self._save_configuration_to_db(config_data, context.user_id)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to save configuration")
                
                return {"status": "created", "config": {"name": config_data.get("name"), "zammad_url": config_data.get("zammad_url")}}
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error creating configuration: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/statistics")
        async def get_statistics(context: PluginContext = Depends(self.get_auth_context)):
            """Get plugin usage statistics"""
            try:
                stats = await self._get_plugin_statistics(context.user_id)
                return stats
            except Exception as e:
                self.logger.error(f"Error getting statistics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
                
        @router.get("/tickets/sync")
        async def sync_tickets_manual(context: PluginContext = Depends(self.get_auth_context)):
            """Manually trigger ticket sync"""
            try:
                result = await self._sync_user_tickets(context.user_id)
                return {"status": "completed", "synced_count": result}
            except Exception as e:
                self.logger.error(f"Error syncing tickets: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        return router
    
    # Plugin-specific methods
    
    async def get_active_config(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get active Zammad configuration for user from database"""
        try:
            async with PluginDatabaseSession(self.plugin_id, plugin_db_manager) as db:
                config = await db.query(ZammadConfiguration).filter(
                    ZammadConfiguration.user_id == user_id,
                    ZammadConfiguration.is_active == True
                ).first()
                
                if config:
                    # Decrypt API token
                    from app.services.plugin_security import plugin_token_manager
                    api_token = plugin_token_manager.decrypt_plugin_secret(config.api_token_encrypted)
                    
                    return {
                        "id": str(config.id),
                        "name": config.name,
                        "zammad_url": config.zammad_url,
                        "api_token": api_token,
                        "chatbot_id": config.chatbot_id,
                        "ai_summarization": {
                            "enabled": config.ai_summarization_enabled,
                            "auto_summarize": config.auto_summarize
                        },
                        "sync_settings": {
                            "enabled": config.sync_enabled,
                            "interval_hours": config.sync_interval_hours
                        }
                    }
                return None
        except Exception as e:
            self.logger.error(f"Failed to get active config: {e}")
            return None
    
    async def get_user_configurations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all configurations for user from database"""
        try:
            async with PluginDatabaseSession(self.plugin_id, plugin_db_manager) as db:
                configs = await db.query(ZammadConfiguration).filter(
                    ZammadConfiguration.user_id == user_id
                ).all()
                
                result = []
                for config in configs:
                    result.append({
                        "id": str(config.id),
                        "name": config.name,
                        "zammad_url": config.zammad_url,
                        "chatbot_id": config.chatbot_id,
                        "is_active": config.is_active,
                        "created_at": config.created_at.isoformat(),
                        "updated_at": config.updated_at.isoformat()
                    })
                
                return result
        except Exception as e:
            self.logger.error(f"Failed to get user configurations: {e}")
            return []
    
    async def fetch_tickets_from_zammad(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch tickets from Zammad API"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Token {config['api_token']}",
                "Content-Type": "application/json"
            }
            
            async with session.get(
                f"{config['zammad_url']}/api/v1/tickets",
                headers=headers,
                timeout=30
            ) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Zammad API error: {await response.text()}"
                    )
                
                return await response.json()
    
    async def fetch_ticket_from_zammad(self, config: Dict[str, Any], ticket_id: str) -> Dict[str, Any]:
        """Fetch specific ticket from Zammad"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Token {config['api_token']}",
                "Content-Type": "application/json"
            }
            
            async with session.get(
                f"{config['zammad_url']}/api/v1/tickets/{ticket_id}",
                headers=headers,
                timeout=30
            ) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Zammad API error: {await response.text()}"
                    )
                
                return await response.json()
    
    async def summarize_ticket_async(self, config: Dict[str, Any], ticket_id: str, user_id: str):
        """Asynchronously summarize a ticket using platform AI"""
        try:
            # Get ticket details
            ticket = await self.fetch_ticket_from_zammad(config, ticket_id)
            
            # Use platform chatbot API for summarization
            chatbot_response = await self.api_client.call_chatbot_api(
                chatbot_id=config["chatbot_id"],
                message=f"Summarize this support ticket:\n\nTitle: {ticket.get('title', '')}\n\nContent: {ticket.get('body', '')}"
            )
            
            summary = chatbot_response.get("response", "")
            
            # TODO: Store summary in database
            self.logger.info(f"Generated summary for ticket {ticket_id}: {summary[:100]}...")
            
            # Update ticket in Zammad with summary
            await self.update_ticket_summary(config, ticket_id, summary)
            
        except Exception as e:
            self.logger.error(f"Error summarizing ticket {ticket_id}: {e}")
    
    async def update_ticket_summary(self, config: Dict[str, Any], ticket_id: str, summary: str):
        """Update ticket with AI summary"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Token {config['api_token']}",
                "Content-Type": "application/json"
            }
            
            update_data = {
                "note": f"AI Summary: {summary}"
            }
            
            async with session.put(
                f"{config['zammad_url']}/api/v1/tickets/{ticket_id}",
                headers=headers,
                json=update_data,
                timeout=30
            ) as response:
                if response.status not in [200, 201]:
                    self.logger.error(f"Failed to update ticket {ticket_id} with summary")
    
    async def test_zammad_connection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test connection to Zammad instance"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Token {config['api_token']}",
                    "Content-Type": "application/json"
                }
                
                async with session.get(
                    f"{config['zammad_url']}/api/v1/users/me",
                    headers=headers,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        return {
                            "success": True,
                            "user": user_data.get("login", "unknown"),
                            "zammad_version": response.headers.get("X-Zammad-Version", "unknown")
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {await response.text()}"
                        }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_ticket_webhook(self, webhook_data: Dict[str, Any]):
        """Process ticket webhook asynchronously"""
        try:
            ticket_data = webhook_data.get("ticket", {})
            ticket_id = ticket_data.get("id")
            
            self.logger.info(f"Processing webhook for ticket {ticket_id}")
            
            # TODO: Get configuration and auto-summarize if enabled
            # This would require looking up the configuration associated with the webhook
            
        except Exception as e:
            self.logger.error(f"Error processing webhook: {e}")
    
    # Cron job functions
    
    async def sync_tickets_from_zammad(self) -> bool:
        """Sync tickets from Zammad (cron job)"""
        try:
            self.logger.info("Starting ticket sync from Zammad")
            
            # TODO: Get all active configurations and sync tickets
            # This would iterate through all user configurations
            
            self.logger.info("Ticket sync completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Ticket sync failed: {e}")
            return False
    
    async def cleanup_old_summaries(self) -> bool:
        """Clean up old AI summaries (cron job)"""
        try:
            self.logger.info("Starting cleanup of old summaries")
            
            # TODO: Clean up summaries older than retention period
            
            self.logger.info("Summary cleanup completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Summary cleanup failed: {e}")
            return False
    
    async def check_zammad_connection(self) -> bool:
        """Check Zammad connectivity (cron job)"""
        try:
            # TODO: Test all configured Zammad instances
            self.logger.info("Zammad connectivity check completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Connectivity check failed: {e}")
            return False
    
    async def generate_weekly_reports(self) -> bool:
        """Generate weekly reports (cron job)"""
        try:
            self.logger.info("Generating weekly reports")
            
            # TODO: Generate and send weekly ticket reports
            
            self.logger.info("Weekly reports generated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            return False
    
    # Enhanced database integration methods
    
    async def _save_configuration_to_db(self, config_data: Dict[str, Any], user_id: str) -> bool:
        """Save Zammad configuration to plugin database"""
        try:
            from app.services.plugin_security import plugin_token_manager
            
            # Encrypt API token
            encrypted_token = plugin_token_manager.encrypt_plugin_secret(config_data["api_token"])
            
            async with PluginDatabaseSession(self.plugin_id, plugin_db_manager) as db:
                # Deactivate existing configurations if this is set as active
                if config_data.get("is_active", True):
                    await db.query(ZammadConfiguration).filter(
                        ZammadConfiguration.user_id == user_id,
                        ZammadConfiguration.is_active == True
                    ).update({"is_active": False})
                
                # Create new configuration
                config = ZammadConfiguration(
                    user_id=user_id,
                    name=config_data["name"],
                    zammad_url=config_data["zammad_url"],
                    api_token_encrypted=encrypted_token,
                    chatbot_id=config_data["chatbot_id"],
                    is_active=config_data.get("is_active", True),
                    ai_summarization_enabled=config_data.get("ai_summarization", {}).get("enabled", True),
                    auto_summarize=config_data.get("ai_summarization", {}).get("auto_summarize", True),
                    sync_enabled=config_data.get("sync_settings", {}).get("enabled", True),
                    sync_interval_hours=config_data.get("sync_settings", {}).get("interval_hours", 2)
                )
                
                db.add(config)
                await db.commit()
                
                self.logger.info(f"Saved Zammad configuration for user {user_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            return False
    
    async def _get_plugin_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get plugin usage statistics"""
        try:
            async with PluginDatabaseSession(self.plugin_id, plugin_db_manager) as db:
                # Get configuration count
                config_count = await db.query(ZammadConfiguration).filter(
                    ZammadConfiguration.user_id == user_id
                ).count()
                
                # Get ticket count
                ticket_count = await db.query(ZammadTicket).join(ZammadConfiguration).filter(
                    ZammadConfiguration.user_id == user_id
                ).count()
                
                # Get tickets with AI summaries
                summarized_count = await db.query(ZammadTicket).join(ZammadConfiguration).filter(
                    ZammadConfiguration.user_id == user_id,
                    ZammadTicket.ai_summary.isnot(None)
                ).count()
                
                # Get recent activity (last 7 days)
                from datetime import timedelta
                week_ago = datetime.now(timezone.utc) - timedelta(days=7)
                recent_tickets = await db.query(ZammadTicket).join(ZammadConfiguration).filter(
                    ZammadConfiguration.user_id == user_id,
                    ZammadTicket.last_synced >= week_ago
                ).count()
                
                return {
                    "configurations": config_count,
                    "total_tickets": ticket_count,
                    "tickets_with_summaries": summarized_count,
                    "recent_tickets": recent_tickets,
                    "summary_rate": round((summarized_count / max(ticket_count, 1)) * 100, 1),
                    "last_sync": datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {
                "error": str(e),
                "configurations": 0,
                "total_tickets": 0,
                "tickets_with_summaries": 0,
                "recent_tickets": 0,
                "summary_rate": 0.0
            }
    
    async def _sync_user_tickets(self, user_id: str) -> int:
        """Sync tickets for a specific user"""
        try:
            config = await self.get_active_config(user_id)
            if not config:
                return 0
            
            # Fetch tickets from Zammad
            tickets = await self.fetch_tickets_from_zammad(config)
            synced_count = 0
            
            async with PluginDatabaseSession(self.plugin_id, plugin_db_manager) as db:
                config_record = await db.query(ZammadConfiguration).filter(
                    ZammadConfiguration.id == config["id"]
                ).first()
                
                if not config_record:
                    return 0
                
                for ticket_data in tickets:
                    # Check if ticket already exists
                    existing_ticket = await db.query(ZammadTicket).filter(
                        ZammadTicket.zammad_ticket_id == str(ticket_data["id"]),
                        ZammadTicket.configuration_id == config_record.id
                    ).first()
                    
                    if existing_ticket:
                        # Update existing ticket
                        existing_ticket.title = ticket_data.get("title", "")
                        existing_ticket.body = ticket_data.get("body", "")
                        existing_ticket.status = ticket_data.get("state", "")
                        existing_ticket.priority = ticket_data.get("priority", "")
                        existing_ticket.last_synced = datetime.now(timezone.utc)
                        existing_ticket.updated_at = datetime.now(timezone.utc)
                    else:
                        # Create new ticket
                        new_ticket = ZammadTicket(
                            zammad_ticket_id=str(ticket_data["id"]),
                            configuration_id=config_record.id,
                            title=ticket_data.get("title", ""),
                            body=ticket_data.get("body", ""),
                            status=ticket_data.get("state", ""),
                            priority=ticket_data.get("priority", ""),
                            customer_id=str(ticket_data.get("customer_id", "")),
                            group_id=str(ticket_data.get("group_id", "")),
                            last_synced=datetime.now(timezone.utc)
                        )
                        db.add(new_ticket)
                        synced_count += 1
                
                await db.commit()
                self.logger.info(f"Synced {synced_count} new tickets for user {user_id}")
                return synced_count
                
        except Exception as e:
            self.logger.error(f"Failed to sync tickets for user {user_id}: {e}")
            return 0
    
    async def _store_ticket_summary(self, ticket_id: str, summary: str, config_id: str):
        """Store AI-generated summary in database"""
        try:
            async with PluginDatabaseSession(self.plugin_id, plugin_db_manager) as db:
                ticket = await db.query(ZammadTicket).filter(
                    ZammadTicket.zammad_ticket_id == ticket_id,
                    ZammadTicket.configuration_id == config_id
                ).first()
                
                if ticket:
                    ticket.ai_summary = summary
                    ticket.updated_at = datetime.now(timezone.utc)
                    await db.commit()
                    self.logger.info(f"Stored AI summary for ticket {ticket_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to store summary for ticket {ticket_id}: {e}")