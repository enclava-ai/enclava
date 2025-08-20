"""
Zammad Integration API endpoints
"""

import asyncio
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from datetime import datetime

from app.db.database import get_db
from app.core.logging import log_api_request
from app.services.module_manager import module_manager
from app.core.security import get_current_user
from app.models.user import User
from app.services.api_key_auth import get_api_key_auth
from app.models.api_key import APIKey
from app.models.chatbot import ChatbotInstance

# Import Zammad models
from modules.zammad.models import (
    ZammadTicket, 
    ZammadProcessingLog, 
    ZammadConfiguration,
    ProcessingStatus
)

router = APIRouter()


class ZammadConfigurationRequest(BaseModel):
    """Request model for creating/updating Zammad configuration"""
    name: str
    description: Optional[str] = None
    is_default: bool = False
    zammad_url: str
    api_token: str
    chatbot_id: str
    process_state: str = "open"
    max_tickets: int = 10
    skip_existing: bool = True
    auto_process: bool = False
    process_interval: int = 30
    summary_template: Optional[str] = None
    custom_settings: Optional[Dict[str, Any]] = {}
    
    @validator('zammad_url')
    def validate_zammad_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Zammad URL must start with http:// or https://')
        return v.rstrip('/')
    
    @validator('max_tickets')
    def validate_max_tickets(cls, v):
        if not 1 <= v <= 100:
            raise ValueError('max_tickets must be between 1 and 100')
        return v
    
    @validator('process_interval')
    def validate_process_interval(cls, v):
        if not 5 <= v <= 1440:
            raise ValueError('process_interval must be between 5 and 1440 minutes')
        return v


class ProcessTicketsRequest(BaseModel):
    """Request model for processing tickets"""
    config_id: Optional[int] = None
    filters: Dict[str, Any] = {}
    
    @validator('filters', pre=True)
    def validate_filters(cls, v):
        """Ensure filters is always a dict"""
        if v is None:
            return {}
        if isinstance(v, list):
            # If someone passes a list, convert to empty dict
            return {}
        if not isinstance(v, dict):
            # If it's some other type, convert to empty dict
            return {}
        return v


class ProcessSingleTicketRequest(BaseModel):
    """Request model for processing a single ticket"""
    ticket_id: int
    config_id: Optional[int] = None


class TestConnectionRequest(BaseModel):
    """Request model for testing Zammad connection"""
    zammad_url: str
    api_token: str


@router.get("/configurations")
async def get_configurations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all Zammad configurations for the current user"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    
    try:
        # Get configurations from database
        stmt = (
            select(ZammadConfiguration)
            .where(ZammadConfiguration.user_id == user_id)
            .where(ZammadConfiguration.is_active == True)
            .order_by(ZammadConfiguration.is_default.desc(), ZammadConfiguration.created_at.desc())
        )
        result = await db.execute(stmt)
        configurations = [config.to_dict() for config in result.scalars()]
        
        return {
            "configurations": configurations,
            "count": len(configurations)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching configurations: {str(e)}")


@router.post("/configurations")
async def create_configuration(
    config_request: ZammadConfigurationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new Zammad configuration"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    
    try:
        # Verify chatbot exists and user has access
        chatbot_stmt = select(ChatbotInstance).where(
            and_(
                ChatbotInstance.id == config_request.chatbot_id,
                ChatbotInstance.created_by == str(user_id),
                ChatbotInstance.is_active == True
            )
        )
        chatbot = await db.scalar(chatbot_stmt)
        if not chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found or access denied")
        
        # Use the module to handle configuration creation
        zammad_module = module_manager.get_module("zammad")
        if not zammad_module:
            raise HTTPException(status_code=503, detail="Zammad module not available")
        
        request_data = {
            "action": "save_configuration",
            "configuration": config_request.dict()
        }
        
        context = {
            "user_id": user_id,
            "user_permissions": current_user.get("permissions", [])
        }
        
        result = await zammad_module.execute_with_interceptors(request_data, context)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating configuration: {str(e)}")


@router.put("/configurations/{config_id}")
async def update_configuration(
    config_id: int,
    config_request: ZammadConfigurationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing Zammad configuration"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    
    try:
        # Check if configuration exists and belongs to user
        stmt = select(ZammadConfiguration).where(
            and_(
                ZammadConfiguration.id == config_id,
                ZammadConfiguration.user_id == user_id
            )
        )
        existing_config = await db.scalar(stmt)
        if not existing_config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        # Verify chatbot exists and user has access
        chatbot_stmt = select(ChatbotInstance).where(
            and_(
                ChatbotInstance.id == config_request.chatbot_id,
                ChatbotInstance.created_by == str(user_id),
                ChatbotInstance.is_active == True
            )
        )
        chatbot = await db.scalar(chatbot_stmt)
        if not chatbot:
            raise HTTPException(status_code=404, detail="Chatbot not found or access denied")
        
        # Deactivate old configuration and create new one (for audit trail)
        existing_config.is_active = False
        
        # Use the module to handle configuration creation
        zammad_module = module_manager.get_module("zammad")
        if not zammad_module:
            raise HTTPException(status_code=503, detail="Zammad module not available")
        
        request_data = {
            "action": "save_configuration",
            "configuration": config_request.dict()
        }
        
        context = {
            "user_id": user_id,
            "user_permissions": current_user.get("permissions", [])
        }
        
        result = await zammad_module.execute_with_interceptors(request_data, context)
        
        await db.commit()
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating configuration: {str(e)}")


@router.delete("/configurations/{config_id}")
async def delete_configuration(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete (deactivate) a Zammad configuration"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    
    try:
        # Check if configuration exists and belongs to user
        stmt = select(ZammadConfiguration).where(
            and_(
                ZammadConfiguration.id == config_id,
                ZammadConfiguration.user_id == user_id
            )
        )
        config = await db.scalar(stmt)
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        # Deactivate instead of deleting (for audit trail)
        config.is_active = False
        config.updated_at = datetime.utcnow()
        
        await db.commit()
        
        return {"message": "Configuration deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting configuration: {str(e)}")


@router.post("/test-connection")
async def test_connection(
    test_request: TestConnectionRequest,
    current_user: User = Depends(get_current_user)
):
    """Test connection to a Zammad instance"""
    try:
        zammad_module = module_manager.get_module("zammad")
        if not zammad_module:
            raise HTTPException(status_code=503, detail="Zammad module not available")
        
        user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
        
        request_data = {
            "action": "test_connection",
            "zammad_url": test_request.zammad_url,
            "api_token": test_request.api_token
        }
        
        context = {
            "user_id": user_id,
            "user_permissions": current_user.get("permissions", [])
        }
        
        result = await zammad_module.execute_with_interceptors(request_data, context)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing connection: {str(e)}")


@router.post("/process")
async def process_tickets(
    process_request: ProcessTicketsRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Process tickets for summarization"""
    try:
        zammad_module = module_manager.get_module("zammad")
        if not zammad_module:
            raise HTTPException(status_code=503, detail="Zammad module not available")
        
        user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
        
        # Debug logging to identify the issue
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Process request filters type: {type(process_request.filters)}")
        logger.info(f"Process request filters value: {process_request.filters}")
        
        # Ensure filters is a dict
        filters = process_request.filters if process_request.filters is not None else {}
        if not isinstance(filters, dict):
            logger.error(f"Filters is not a dict: {type(filters)} = {filters}")
            filters = {}
        
        request_data = {
            "action": "process_tickets",
            "config_id": process_request.config_id,
            "filters": filters
        }
        
        context = {
            "user_id": user_id,
            "user_permissions": current_user.get("permissions", [])
        }
        
        # Execute processing in background for large batches
        if filters.get("limit", 10) > 5:
            # Start background task
            background_tasks.add_task(
                _process_tickets_background,
                zammad_module,
                request_data,
                context
            )
            
            return {
                "message": "Processing started in background",
                "status": "started"
            }
        else:
            # Process immediately for small batches
            result = await zammad_module.execute_with_interceptors(request_data, context)
            return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting ticket processing: {str(e)}")


@router.post("/tickets/{ticket_id}/process")
async def process_single_ticket(
    ticket_id: int,
    process_request: ProcessSingleTicketRequest,
    current_user: User = Depends(get_current_user)
):
    """Process a single ticket for summarization"""
    try:
        zammad_module = module_manager.get_module("zammad")
        if not zammad_module:
            raise HTTPException(status_code=503, detail="Zammad module not available")
        
        user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
        
        request_data = {
            "action": "process_single_ticket",
            "ticket_id": ticket_id,
            "config_id": process_request.config_id
        }
        
        context = {
            "user_id": user_id,
            "user_permissions": current_user.get("permissions", [])
        }
        
        result = await zammad_module.execute_with_interceptors(request_data, context)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing ticket: {str(e)}")


@router.get("/tickets/{ticket_id}/summary")
async def get_ticket_summary(
    ticket_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get the AI summary for a specific ticket"""
    try:
        zammad_module = module_manager.get_module("zammad")
        if not zammad_module:
            raise HTTPException(status_code=503, detail="Zammad module not available")
        
        user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
        
        request_data = {
            "action": "get_ticket_summary",
            "ticket_id": ticket_id
        }
        
        context = {
            "user_id": user_id,
            "user_permissions": current_user.get("permissions", [])
        }
        
        result = await zammad_module.execute_with_interceptors(request_data, context)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting ticket summary: {str(e)}")


@router.get("/tickets")
async def get_processed_tickets(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of processed tickets"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    
    try:
        # Build query
        query = select(ZammadTicket).where(ZammadTicket.processed_by_user_id == user_id)
        
        if status:
            query = query.where(ZammadTicket.processing_status == status)
        
        query = query.order_by(desc(ZammadTicket.processed_at))
        query = query.offset(offset).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        tickets = [ticket.to_dict() for ticket in result.scalars()]
        
        # Get total count
        count_query = select(ZammadTicket).where(ZammadTicket.processed_by_user_id == user_id)
        if status:
            count_query = count_query.where(ZammadTicket.processing_status == status)
        
        total_result = await db.execute(count_query)
        total_count = len(list(total_result.scalars()))
        
        return {
            "tickets": tickets,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tickets: {str(e)}")


@router.get("/status")
async def get_module_status(
    current_user: User = Depends(get_current_user)
):
    """Get Zammad module status and statistics"""
    try:
        zammad_module = module_manager.get_module("zammad")
        if not zammad_module:
            raise HTTPException(status_code=503, detail="Zammad module not available")
        
        user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
        
        request_data = {
            "action": "get_status"
        }
        
        context = {
            "user_id": user_id,
            "user_permissions": current_user.get("permissions", [])
        }
        
        result = await zammad_module.execute_with_interceptors(request_data, context)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting module status: {str(e)}")


@router.get("/processing-logs")
async def get_processing_logs(
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get processing logs for the current user"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    
    try:
        # Get processing logs
        query = (
            select(ZammadProcessingLog)
            .where(ZammadProcessingLog.initiated_by_user_id == user_id)
            .order_by(desc(ZammadProcessingLog.started_at))
            .offset(offset)
            .limit(limit)
        )
        
        result = await db.execute(query)
        logs = [log.to_dict() for log in result.scalars()]
        
        # Get total count
        count_query = select(ZammadProcessingLog).where(
            ZammadProcessingLog.initiated_by_user_id == user_id
        )
        total_result = await db.execute(count_query)
        total_count = len(list(total_result.scalars()))
        
        return {
            "logs": logs,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching processing logs: {str(e)}")


@router.get("/chatbots")
async def get_available_chatbots(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of chatbots available for Zammad integration"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    
    try:
        # Get user's active chatbots
        stmt = (
            select(ChatbotInstance)
            .where(ChatbotInstance.created_by == str(user_id))
            .where(ChatbotInstance.is_active == True)
            .order_by(ChatbotInstance.name)
        )
        
        result = await db.execute(stmt)
        chatbots = []
        
        for chatbot in result.scalars():
            # Extract chatbot_type from config JSON or provide default
            config = chatbot.config or {}
            chatbot_type = config.get('chatbot_type', 'general')
            model = config.get('model', 'Unknown')
            
            chatbots.append({
                "id": chatbot.id,
                "name": chatbot.name,
                "chatbot_type": chatbot_type,
                "model": model,
                "description": chatbot.description or ''
            })
        
        return {
            "chatbots": chatbots,
            "count": len(chatbots)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching chatbots: {str(e)}")


async def _process_tickets_background(zammad_module, request_data: Dict[str, Any], context: Dict[str, Any]):
    """Background task for processing tickets"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Starting background ticket processing with request_data: {request_data}")
        logger.info(f"Context: {context}")
        await zammad_module.execute_with_interceptors(request_data, context)
    except Exception as e:
        # Log error but don't raise - this is a background task
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Background ticket processing failed: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")


# API key authentication endpoints (for programmatic access)

@router.post("/api-key/process", dependencies=[Depends(get_api_key_auth)])
async def api_process_tickets(
    process_request: ProcessTicketsRequest,
    api_key_context: Dict = Depends(get_api_key_auth)
):
    """Process tickets using API key authentication"""
    try:
        zammad_module = module_manager.get_module("zammad")
        if not zammad_module:
            raise HTTPException(status_code=503, detail="Zammad module not available")
        
        user_id = api_key_context["user_id"]
        
        request_data = {
            "action": "process_tickets",
            "config_id": process_request.config_id,
            "filters": process_request.filters
        }
        
        context = {
            "user_id": user_id,
            "api_key_id": api_key_context["api_key_id"],
            "user_permissions": ["modules:*"]  # API keys get full module access
        }
        
        result = await zammad_module.execute_with_interceptors(request_data, context)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing tickets: {str(e)}")


@router.get("/api-key/status", dependencies=[Depends(get_api_key_auth)])
async def api_get_status(
    api_key_context: Dict = Depends(get_api_key_auth)
):
    """Get module status using API key authentication"""
    try:
        zammad_module = module_manager.get_module("zammad")
        if not zammad_module:
            raise HTTPException(status_code=503, detail="Zammad module not available")
        
        user_id = api_key_context["user_id"]
        
        request_data = {
            "action": "get_status"
        }
        
        context = {
            "user_id": user_id,
            "api_key_id": api_key_context["api_key_id"],
            "user_permissions": ["modules:*"]  # API keys get full module access
        }
        
        result = await zammad_module.execute_with_interceptors(request_data, context)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")