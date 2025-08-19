"""
Embedding Service
Provides text embedding functionality using LiteLLM proxy
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using LiteLLM"""
    
    def __init__(self, model_name: str = "privatemode-embeddings"):
        self.model_name = model_name
        self.litellm_client = None
        self.dimension = 1024  # Actual dimension for privatemode-embeddings
        self.initialized = False
        
    async def initialize(self):
        """Initialize the embedding service with LiteLLM"""
        try:
            from app.services.litellm_client import litellm_client
            self.litellm_client = litellm_client
            
            # Test connection to LiteLLM
            health = await self.litellm_client.health_check()
            if health.get("status") == "unhealthy":
                logger.error(f"LiteLLM service unhealthy: {health.get('error')}")
                return False
            
            self.initialized = True
            logger.info(f"Embedding service initialized with LiteLLM: {self.model_name} (dimension: {self.dimension})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize LiteLLM embedding service: {e}")
            logger.warning("Using fallback random embeddings")
            return False
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text"""
        embeddings = await self.get_embeddings([text])
        return embeddings[0]
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts using LiteLLM"""
        if not self.initialized or not self.litellm_client:
            # Fallback to random embeddings if not initialized
            logger.warning("LiteLLM not available, using random embeddings")
            return self._generate_fallback_embeddings(texts)
        
        try:
            embeddings = []
            # Process texts in batches for efficiency
            batch_size = 10
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i+batch_size]
                
                # Process each text in the batch
                batch_embeddings = []
                for text in batch:
                    try:
                        # Truncate text if it's too long for the model's context window
                        # privatemode-embeddings has a 512 token limit, truncate to ~400 tokens worth of chars
                        # Rough estimate: 1 token ≈ 4 characters, so 400 tokens ≈ 1600 chars
                        max_chars = 1600
                        if len(text) > max_chars:
                            truncated_text = text[:max_chars]
                            logger.debug(f"Truncated text from {len(text)} to {max_chars} chars for embedding")
                        else:
                            truncated_text = text
                        
                        # Call LiteLLM embedding endpoint
                        response = await self.litellm_client.create_embedding(
                            model=self.model_name,
                            input_text=truncated_text,
                            user_id="rag_system",
                            api_key_id=0  # System API key
                        )
                        
                        # Extract embedding from response
                        if "data" in response and len(response["data"]) > 0:
                            embedding = response["data"][0].get("embedding", [])
                            if embedding:
                                batch_embeddings.append(embedding)
                                # Update dimension based on actual embedding size
                                if not hasattr(self, '_dimension_confirmed'):
                                    self.dimension = len(embedding)
                                    self._dimension_confirmed = True
                                    logger.info(f"Confirmed embedding dimension: {self.dimension}")
                            else:
                                logger.warning(f"No embedding in response for text: {text[:50]}...")
                                batch_embeddings.append(self._generate_fallback_embedding(text))
                        else:
                            logger.warning(f"Invalid response structure for text: {text[:50]}...")
                            batch_embeddings.append(self._generate_fallback_embedding(text))
                    except Exception as e:
                        logger.error(f"Error getting embedding for text: {e}")
                        batch_embeddings.append(self._generate_fallback_embedding(text))
                
                embeddings.extend(batch_embeddings)
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings with LiteLLM: {e}")
            # Fallback to random embeddings
            return self._generate_fallback_embeddings(texts)
    
    def _generate_fallback_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate fallback random embeddings when model unavailable"""
        embeddings = []
        for text in texts:
            embeddings.append(self._generate_fallback_embedding(text))
        return embeddings
    
    def _generate_fallback_embedding(self, text: str) -> List[float]:
        """Generate a single fallback embedding"""
        dimension = self.dimension or 1024  # Default dimension for privatemode-embeddings
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
            "backend": "LiteLLM",
            "initialized": self.initialized
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        self.initialized = False
        self.litellm_client = None


# Global embedding service instance
embedding_service = EmbeddingService()