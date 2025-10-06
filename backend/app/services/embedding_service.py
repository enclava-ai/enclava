"""
Embedding Service
Provides text embedding functionality using LLM service
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using LLM service"""
    
    def __init__(self, model_name: str = "intfloat/multilingual-e5-large-instruct"):
        self.model_name = model_name
        self.dimension = 1024  # Actual dimension for intfloat/multilingual-e5-large-instruct
        self.initialized = False
        
    async def initialize(self):
        """Initialize the embedding service with LLM service"""
        try:
            from app.services.llm.service import llm_service
            
            # Initialize LLM service if not already done
            if not llm_service._initialized:
                await llm_service.initialize()
            
            # Test LLM service health
            if not llm_service._initialized:
                logger.error("LLM service not initialized")
                return False

            # Check if PrivateMode provider is available
            try:
                provider_status = await llm_service.get_provider_status()
                privatemode_status = provider_status.get("privatemode")
                if not privatemode_status or privatemode_status.status != "healthy":
                    logger.error(f"PrivateMode provider not available: {privatemode_status}")
                    return False
            except Exception as e:
                logger.error(f"Failed to check provider status: {e}")
                return False
            
            self.initialized = True
            logger.info(f"Embedding service initialized with LLM service: {self.model_name} (dimension: {self.dimension})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM embedding service: {e}")
            logger.warning("Using fallback random embeddings")
            return False
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text"""
        embeddings = await self.get_embeddings([text])
        return embeddings[0]
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts using LLM service"""
        if not self.initialized:
            # Fallback to random embeddings if not initialized
            logger.warning("LLM service not available, using random embeddings")
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
                        # intfloat/multilingual-e5-large-instruct has a 512 token limit, truncate to ~400 tokens worth of chars
                        # Rough estimate: 1 token ≈ 4 characters, so 400 tokens ≈ 1600 chars
                        max_chars = 1600
                        if len(text) > max_chars:
                            truncated_text = text[:max_chars]
                            logger.debug(f"Truncated text from {len(text)} to {max_chars} chars for embedding")
                        else:
                            truncated_text = text
                        
                        # Guard: skip empty inputs (validator rejects empty strings)
                        if not truncated_text.strip():
                            logger.debug("Empty input for embedding; using fallback vector")
                            batch_embeddings.append(self._generate_fallback_embedding(text))
                            continue

                        # Call LLM service embedding endpoint
                        from app.services.llm.service import llm_service
                        from app.services.llm.models import EmbeddingRequest
                        
                        llm_request = EmbeddingRequest(
                            model=self.model_name,
                            input=truncated_text,
                            user_id="rag_system",
                            api_key_id=0  # System API key
                        )
                        
                        response = await llm_service.create_embedding(llm_request)
                        
                        # Extract embedding from response
                        if response.data and len(response.data) > 0:
                            embedding = response.data[0].embedding
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
            logger.error(f"Error generating embeddings with LLM service: {e}")
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
        dimension = self.dimension or 1024  # Default dimension for intfloat/multilingual-e5-large-instruct
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
            "backend": "LLM Service",
            "initialized": self.initialized
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        # Cleanup LLM service to prevent memory leaks
        try:
            from .llm.service import llm_service
            if llm_service._initialized:
                await llm_service.cleanup()
                logger.info("Cleaned up LLM service from embedding service")
        except Exception as e:
            logger.error(f"Error cleaning up LLM service: {e}")

        self.initialized = False


# Global embedding service instance
embedding_service = EmbeddingService()
