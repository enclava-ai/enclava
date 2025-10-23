"""
Ollama Embedding Service
Provides text embedding functionality using Ollama locally
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class OllamaEmbeddingService:
    """Service for generating text embeddings using Ollama"""

    def __init__(self, model_name: str = "bge-m3", base_url: str = "http://172.17.0.1:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self.dimension = 1024  # bge-m3 dimension
        self.initialized = False
        self._session = None

    async def initialize(self):
        """Initialize embedding service with Ollama"""
        try:
            # Create HTTP session
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60)
            )

            # Test Ollama is running and model is available
            async with self._session.get(f"{self.base_url}/api/tags") as resp:
                if resp.status != 200:
                    logger.error(f"Ollama not responding at {self.base_url}")
                    return False

                data = await resp.json()
                models = [model['name'].split(':')[0] for model in data.get('models', [])]

                if self.model_name not in models:
                    logger.error(f"Model {self.model_name} not found in Ollama. Available: {models}")
                    return False

            # Test embedding generation
            test_embedding = await self.get_embedding("test")
            if not test_embedding or len(test_embedding) != self.dimension:
                logger.error(f"Failed to generate test embedding with {self.model_name}")
                return False

            self.initialized = True
            logger.info(f"Ollama embedding service initialized with model: {self.model_name} (dimension: {self.dimension})")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Ollama embedding service: {e}")
            return False

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text"""
        embeddings = await self.get_embeddings([text])
        return embeddings[0]

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts using Ollama"""
        if not self.initialized:
            # Try to initialize if not done
            if not await self.initialize():
                logger.error("Ollama embedding service not available")
                return self._generate_fallback_embeddings(texts)

        try:
            embeddings = []

            # Process each text individually (Ollama API typically processes one at a time)
            for text in texts:
                try:
                    # Skip empty inputs
                    if not text.strip():
                        logger.debug("Empty input for embedding; using fallback vector")
                        embeddings.append(self._generate_fallback_embedding(text))
                        continue

                    # Call Ollama embedding API
                    async with self._session.post(
                        f"{self.base_url}/api/embeddings",
                        json={
                            "model": self.model_name,
                            "prompt": text
                        }
                    ) as resp:
                        if resp.status != 200:
                            logger.error(f"Ollama embedding request failed: {resp.status}")
                            embeddings.append(self._generate_fallback_embedding(text))
                            continue

                        result = await resp.json()

                        if 'embedding' in result:
                            embedding = result['embedding']
                            if len(embedding) == self.dimension:
                                embeddings.append(embedding)
                            else:
                                logger.warning(f"Embedding dimension mismatch: expected {self.dimension}, got {len(embedding)}")
                                embeddings.append(self._generate_fallback_embedding(text))
                        else:
                            logger.error(f"No embedding in Ollama response for text: {text[:50]}...")
                            embeddings.append(self._generate_fallback_embedding(text))

                except Exception as e:
                    logger.error(f"Error getting embedding from Ollama for text: {e}")
                    embeddings.append(self._generate_fallback_embedding(text))

            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings with Ollama: {e}")
            return self._generate_fallback_embeddings(texts)

    def _generate_fallback_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate fallback random embeddings when Ollama unavailable"""
        embeddings = []
        for text in texts:
            embeddings.append(self._generate_fallback_embedding(text))
        return embeddings

    def _generate_fallback_embedding(self, text: str) -> List[float]:
        """Generate a single fallback embedding"""
        dimension = self.dimension  # 1024 for bge-m3
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
            "backend": "Ollama",
            "base_url": self.base_url,
            "initialized": self.initialized
        }

    async def cleanup(self):
        """Cleanup resources"""
        if self._session:
            await self._session.close()
        self.initialized = False


# Global Ollama embedding service instance
ollama_embedding_service = OllamaEmbeddingService()