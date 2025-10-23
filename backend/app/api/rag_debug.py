"""
RAG Debug API endpoints for testing and debugging
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
import logging

from app.core.security import get_current_user
from app.core.config import settings
from app.modules.rag.main import RAGModule
from app.models.user import User

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.get("/collections")
async def list_collections(
    current_user: User = Depends(get_current_user)
):
    """List all available RAG collections"""
    try:
        from app.services.qdrant_stats_service import qdrant_stats_service

        # Get collections from Qdrant (same as main RAG API)
        stats_data = await qdrant_stats_service.get_collections_stats()
        collections = stats_data.get("collections", [])

        # Extract collection names
        collection_names = [col["name"] for col in collections]

        return {
            "collections": collection_names,
            "count": len(collection_names)
        }

    except Exception as e:
        logger.error(f"List collections error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def debug_search(
    query: str = Query(..., description="Search query"),
    max_results: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    score_threshold: float = Query(0.3, ge=0.0, le=1.0, description="Minimum score threshold"),
    collection_name: Optional[str] = Query(None, description="Collection name to search"),
    config: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user)
):
    """Debug search endpoint with detailed information"""
    try:
        # Get configuration
        app_config = settings

        # Initialize RAG module with BGE-M3 configuration
        rag_config = {
            "embedding_model": "BAAI/bge-m3"
        }
        rag_module = RAGModule(app_config, config=rag_config)

        # Get available collections if none specified
        if not collection_name:
            collections = await rag_module.list_collections()
            if collections:
                collection_name = collections[0]  # Use first collection
            else:
                return {
                    "results": [],
                    "debug_info": {
                        "error": "No collections available",
                        "collections_found": 0
                    },
                    "search_time_ms": 0
                }

        # Perform search
        results = await rag_module.search(
            query=query,
            max_results=max_results,
            score_threshold=score_threshold,
            collection_name=collection_name,
            config=config or {}
        )

        return results

    except Exception as e:
        logger.error(f"Debug search error: {e}")
        return {
            "results": [],
            "debug_info": {
                "error": str(e),
                "query": query,
                "collection_name": collection_name
            },
            "search_time_ms": 0
        }