"""
Embedding Service
Provides local sentence-transformer embeddings (default: BAAI/bge-small-en).
Falls back to deterministic random vectors when the local model is unavailable.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using a local transformer model"""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or getattr(settings, "RAG_EMBEDDING_MODEL", "BAAI/bge-small-en")
        self.dimension = 384  # bge-small produces 384-d vectors
        self.initialized = False
        self.local_model = None
        self.backend = "uninitialized"

    async def initialize(self):
        """Initialize the embedding service with LLM service"""
        try:
            from sentence_transformers import SentenceTransformer

            loop = asyncio.get_running_loop()

            def load_model():
                # Load model synchronously in a worker thread to avoid blocking event loop
                return SentenceTransformer(self.model_name)

            self.local_model = await loop.run_in_executor(None, load_model)
            self.dimension = self.local_model.get_sentence_embedding_dimension()
            self.initialized = True
            self.backend = "sentence_transformer"
            logger.info(
                "Embedding service initialized with local model %s (dimension: %s)",
                self.model_name,
                self.dimension,
            )
            return True

        except ImportError as exc:
            logger.error("sentence-transformers not installed: %s", exc)
            logger.warning("Falling back to random embeddings")
            self.local_model = None
            self.initialized = False
            self.backend = "fallback_random"
            return False

        except Exception as exc:
            logger.error(f"Failed to load local embedding model {self.model_name}: {exc}")
            logger.warning("Falling back to random embeddings")
            self.local_model = None
            self.initialized = False
            self.backend = "fallback_random"
            return False
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text"""
        embeddings = await self.get_embeddings([text])
        return embeddings[0]

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts using LLM service"""
        start_time = time.time()

        if self.local_model:
            if not texts:
                return []

            loop = asyncio.get_running_loop()

            try:
                embeddings = await loop.run_in_executor(
                    None,
                    lambda: self.local_model.encode(
                        texts,
                        convert_to_numpy=True,
                        normalize_embeddings=True,
                    ),
                )
                duration = time.time() - start_time
                logger.info(
                    "Embedding batch completed",
                    extra={
                        "backend": self.backend,
                        "model": self.model_name,
                        "count": len(texts),
                        "dimension": self.dimension,
                        "duration_sec": round(duration, 4),
                    },
                )
                return embeddings.tolist()
            except Exception as exc:
                logger.error(f"Local embedding generation failed: {exc}")
                self.backend = "fallback_random"
                return self._generate_fallback_embeddings(texts, duration=time.time() - start_time)

        logger.warning("Local embedding model unavailable; using fallback random embeddings")
        self.backend = "fallback_random"
        return self._generate_fallback_embeddings(texts, duration=time.time() - start_time)
    
    def _generate_fallback_embeddings(self, texts: List[str], duration: float = None) -> List[List[float]]:
        """Generate fallback random embeddings when model unavailable"""
        embeddings = []
        for text in texts:
            embeddings.append(self._generate_fallback_embedding(text))
        logger.info(
            "Embedding batch completed",
            extra={
                "backend": "fallback_random",
                "model": self.model_name,
                "count": len(texts),
                "dimension": self.dimension,
                "duration_sec": round(duration or 0.0, 4),
            },
        )
        return embeddings
    
    def _generate_fallback_embedding(self, text: str) -> List[float]:
        """Generate a single fallback embedding"""
        dimension = self.dimension or 384
        # Use hash for reproducible random embeddings
        np.random.seed(hash(text) % 2**32)
        return np.random.random(dimension).tolist()
    
    async def similarity(self, text1: str, text2: str) -> float:
        """Calculate cosine similarity between two texts"""
        embeddings = await self.get_embeddings([text1, text2])
        
        # Calculate cosine similarity
        vec1 = np.array(embeddings[0])
        vec2 = np.array(embeddings[1])
        
        # Normalize vectors
        vec1_norm = vec1 / np.linalg.norm(vec1)
        vec2_norm = vec2 / np.linalg.norm(vec2)
        
        # Calculate cosine similarity
        similarity = np.dot(vec1_norm, vec2_norm)
        return float(similarity)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get embedding service statistics"""
        return {
            "model_name": self.model_name,
            "model_loaded": self.initialized,
            "dimension": self.dimension,
            "backend": self.backend,
            "initialized": self.initialized
        }

    async def cleanup(self):
        """Cleanup resources"""
        self.local_model = None
        self.initialized = False
        self.backend = "uninitialized"


# Global embedding service instance
embedding_service = EmbeddingService()
