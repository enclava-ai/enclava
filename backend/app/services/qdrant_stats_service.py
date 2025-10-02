"""
Qdrant Stats Service
Provides direct, live statistics from Qdrant vector database
This is the single source of truth for all RAG collection statistics
"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class QdrantStatsService:
    """Service for getting live statistics from Qdrant"""

    def __init__(self):
        self.qdrant_host = getattr(settings, 'QDRANT_HOST', 'enclava-qdrant')
        self.qdrant_port = getattr(settings, 'QDRANT_PORT', 6333)
        self.qdrant_url = f"http://{self.qdrant_host}:{self.qdrant_port}"

    async def get_collections_stats(self) -> Dict[str, Any]:
        """Get live collection statistics directly from Qdrant"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get all collections
                response = await client.get(f"{self.qdrant_url}/collections")
                if response.status_code != 200:
                    logger.error(f"Failed to get collections: {response.status_code}")
                    return {"collections": [], "total_documents": 0, "total_size_bytes": 0}

                data = response.json()
                result = data.get("result", {})
                collections_data = result.get("collections", [])

                collections = []
                total_documents = 0
                total_size_bytes = 0

                # Get detailed info for each collection
                for col_info in collections_data:
                    collection_name = col_info.get("name", "")
                    # Include all collections, not just rag_ ones

                    # Get detailed collection info
                    try:
                        detail_response = await client.get(f"{self.qdrant_url}/collections/{collection_name}")
                        if detail_response.status_code == 200:
                            detail_data = detail_response.json()
                            detail_result = detail_data.get("result", {})

                            points_count = detail_result.get("points_count", 0)
                            status = detail_result.get("status", "unknown")

                            # Get vector size for size calculation
                            vector_size = 1024  # Default for multilingual-e5-large
                            try:
                                config = detail_result.get("config", {})
                                params = config.get("params", {})
                                vectors = params.get("vectors", {})
                                if isinstance(vectors, dict) and "size" in vectors:
                                    vector_size = vectors["size"]
                                elif isinstance(vectors, dict) and "default" in vectors:
                                    vector_size = vectors["default"].get("size", 1024)
                            except Exception:
                                pass

                            # Estimate size (points * vector_size * 4 bytes + 20% metadata overhead)
                            estimated_size = int(points_count * vector_size * 4 * 1.2)

                            # Extract collection metadata for user-friendly name
                            display_name = collection_name
                            description = ""

                            # Parse collection name to get original name
                            if collection_name.startswith("rag_"):
                                parts = collection_name[4:].split("_")
                                if len(parts) > 1:
                                    # Remove the UUID suffix
                                    uuid_parts = [p for p in parts if len(p) == 8 and all(c in '0123456789abcdef' for c in p)]
                                    for uuid_part in uuid_parts:
                                        parts.remove(uuid_part)
                                    display_name = " ".join(parts).replace("_", " ").title()

                            collection_stat = {
                                "id": collection_name,
                                "name": display_name,
                                "description": description,
                                "document_count": points_count,
                                "vector_count": points_count,
                                "size_bytes": estimated_size,
                                "status": status,
                                "qdrant_collection_name": collection_name,
                                "created_at": "",  # Not available from Qdrant
                                "updated_at": datetime.utcnow().isoformat(),
                                "is_active": status == "green",
                                "is_managed": True,
                                "source": "qdrant"
                            }

                            collections.append(collection_stat)
                            total_documents += points_count
                            total_size_bytes += estimated_size

                    except Exception as e:
                        logger.error(f"Error getting details for collection {collection_name}: {e}")
                        continue

                return {
                    "collections": collections,
                    "total_documents": total_documents,
                    "total_size_bytes": total_size_bytes,
                    "total_collections": len(collections)
                }

        except Exception as e:
            logger.error(f"Error getting Qdrant stats: {e}")
            return {"collections": [], "total_documents": 0, "total_size_bytes": 0, "total_collections": 0}

    async def get_collection_stats(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific collection"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.qdrant_url}/collections/{collection_name}")
                if response.status_code != 200:
                    return None

                data = response.json()
                result = data.get("result", {})

                points_count = result.get("points_count", 0)
                status = result.get("status", "unknown")

                # Get vector size
                vector_size = 1024
                try:
                    config = result.get("config", {})
                    params = config.get("params", {})
                    vectors = params.get("vectors", {})
                    if isinstance(vectors, dict) and "size" in vectors:
                        vector_size = vectors["size"]
                except Exception:
                    pass

                estimated_size = int(points_count * vector_size * 4 * 1.2)

                return {
                    "document_count": points_count,
                    "vector_count": points_count,
                    "size_bytes": estimated_size,
                    "status": status
                }

        except Exception as e:
            logger.error(f"Error getting collection stats for {collection_name}: {e}")
            return None


# Global instance
qdrant_stats_service = QdrantStatsService()