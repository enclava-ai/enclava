"""
Debugging API endpoints for troubleshooting chatbot issues
"""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.models.chatbot import ChatbotInstance, PromptTemplate
from app.models.rag_collection import RagCollection

router = APIRouter()


@router.get("/chatbot/{chatbot_id}/config")
async def get_chatbot_config_debug(
    chatbot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed configuration for debugging a specific chatbot"""

    # Get chatbot instance
    chatbot = db.query(ChatbotInstance).filter(
        ChatbotInstance.id == chatbot_id,
        ChatbotInstance.user_id == current_user.id
    ).first()

    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    # Get prompt template
    prompt_template = db.query(PromptTemplate).filter(
        PromptTemplate.type == chatbot.chatbot_type
    ).first()

    # Get RAG collections if configured
    rag_collections = []
    if chatbot.rag_collection_ids:
        collection_ids = chatbot.rag_collection_ids
        if isinstance(collection_ids, str):
            import json
            try:
                collection_ids = json.loads(collection_ids)
            except:
                collection_ids = []

        if collection_ids:
            collections = db.query(RagCollection).filter(
                RagCollection.id.in_(collection_ids)
            ).all()
            rag_collections = [
                {
                    "id": col.id,
                    "name": col.name,
                    "document_count": col.document_count,
                    "qdrant_collection_name": col.qdrant_collection_name,
                    "is_active": col.is_active
                }
                for col in collections
            ]

    # Get recent conversations count
    from app.models.chatbot import ChatbotConversation
    conversation_count = db.query(ChatbotConversation).filter(
        ChatbotConversation.chatbot_instance_id == chatbot_id
    ).count()

    return {
        "chatbot": {
            "id": chatbot.id,
            "name": chatbot.name,
            "type": chatbot.chatbot_type,
            "description": chatbot.description,
            "created_at": chatbot.created_at,
            "is_active": chatbot.is_active,
            "conversation_count": conversation_count
        },
        "prompt_template": {
            "type": prompt_template.type if prompt_template else None,
            "system_prompt": prompt_template.system_prompt if prompt_template else None,
            "variables": prompt_template.variables if prompt_template else []
        },
        "rag_collections": rag_collections,
        "configuration": {
            "max_tokens": chatbot.max_tokens,
            "temperature": chatbot.temperature,
            "streaming": chatbot.streaming,
            "memory_config": chatbot.memory_config
        }
    }


@router.get("/chatbot/{chatbot_id}/test-rag")
async def test_rag_search(
    chatbot_id: str,
    query: str = "test query",
    top_k: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test RAG search for a specific chatbot"""

    # Get chatbot instance
    chatbot = db.query(ChatbotInstance).filter(
        ChatbotInstance.id == chatbot_id,
        ChatbotInstance.user_id == current_user.id
    ).first()

    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    # Test RAG search
    try:
        from app.modules.rag.main import rag_module

        # Get collection IDs
        collection_ids = []
        if chatbot.rag_collection_ids:
            if isinstance(chatbot.rag_collection_ids, str):
                import json
                try:
                    collection_ids = json.loads(chatbot.rag_collection_ids)
                except:
                    pass
            elif isinstance(chatbot.rag_collection_ids, list):
                collection_ids = chatbot.rag_collection_ids

        if not collection_ids:
            return {
                "query": query,
                "results": [],
                "message": "No RAG collections configured for this chatbot"
            }

        # Perform search
        search_results = await rag_module.search(
            query=query,
            collection_ids=collection_ids,
            top_k=top_k,
            score_threshold=0.5
        )

        return {
            "query": query,
            "results": search_results,
            "collections_searched": collection_ids,
            "result_count": len(search_results)
        }

    except Exception as e:
        return {
            "query": query,
            "results": [],
            "error": str(e),
            "message": "RAG search failed"
        }


@router.get("/system/status")
async def get_system_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get system status for debugging"""

    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check module status
    module_status = {}
    try:
        from app.services.module_manager import module_manager
        modules = module_manager.list_modules()
        for module_name, module_info in modules.items():
            module_status[module_name] = {
                "status": module_info.get("status", "unknown"),
                "enabled": module_info.get("enabled", False)
            }
    except Exception as e:
        module_status = {"error": str(e)}

    # Check Redis (if configured)
    redis_status = "not configured"
    try:
        from app.core.cache import core_cache
        await core_cache.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    # Check Qdrant (if configured)
    qdrant_status = "not configured"
    try:
        from app.services.qdrant_service import qdrant_service
        collections = await qdrant_service.list_collections()
        qdrant_status = f"healthy ({len(collections)} collections)"
    except Exception as e:
        qdrant_status = f"error: {str(e)}"

    return {
        "database": db_status,
        "modules": module_status,
        "redis": redis_status,
        "qdrant": qdrant_status,
        "timestamp": "UTC"
    }