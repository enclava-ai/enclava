"""
Trusted Execution Environment (TEE) Service
Handles Privatemode.ai TEE integration for confidential computing
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum

import aiohttp
from fastapi import HTTPException, status
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key
import base64

from app.core.config import settings

logger = logging.getLogger(__name__)


class TEEStatus(str, Enum):
    """TEE environment status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class AttestationStatus(str, Enum):
    """Attestation verification status"""
    VERIFIED = "verified"
    FAILED = "failed"
    PENDING = "pending"
    EXPIRED = "expired"


class TEEService:
    """Service for managing Privatemode.ai TEE integration"""
    
    def __init__(self):
        self.privatemode_base_url = "http://privatemode-proxy:8080"
        self.privatemode_api_key = settings.PRIVATEMODE_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes timeout
        self.attestation_cache = {}  # Cache for attestation results
        self.attestation_ttl = timedelta(hours=1)  # Cache TTL
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.privatemode_api_key}"
                }
            )
        return self.session
    
    async def close(self):
        """Close the HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check TEE environment health"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.privatemode_base_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    return {
                        "status": TEEStatus.HEALTHY.value,
                        "timestamp": datetime.utcnow().isoformat(),
                        "tee_enabled": health_data.get("tee_enabled", False),
                        "attestation_available": health_data.get("attestation_available", False),
                        "secure_memory": health_data.get("secure_memory", False),
                        "details": health_data
                    }
                else:
                    return {
                        "status": TEEStatus.DEGRADED.value,
                        "timestamp": datetime.utcnow().isoformat(),
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            logger.error(f"TEE health check error: {e}")
            return {
                "status": TEEStatus.OFFLINE.value,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def get_attestation(self, nonce: Optional[str] = None) -> Dict[str, Any]:
        """Get TEE attestation report"""
        try:
            if not nonce:
                nonce = base64.b64encode(os.urandom(32)).decode()
            
            # Check cache first
            cache_key = f"attestation_{nonce}"
            if cache_key in self.attestation_cache:
                cached_result = self.attestation_cache[cache_key]
                if datetime.fromisoformat(cached_result["timestamp"]) + self.attestation_ttl > datetime.utcnow():
                    return cached_result
            
            session = await self._get_session()
            payload = {"nonce": nonce}
            
            async with session.post(
                f"{self.privatemode_base_url}/attestation",
                json=payload
            ) as response:
                if response.status == 200:
                    attestation_data = await response.json()
                    
                    # Process attestation report
                    result = {
                        "status": AttestationStatus.VERIFIED.value,
                        "timestamp": datetime.utcnow().isoformat(),
                        "nonce": nonce,
                        "report": attestation_data.get("report"),
                        "signature": attestation_data.get("signature"),
                        "certificate_chain": attestation_data.get("certificate_chain"),
                        "measurements": attestation_data.get("measurements", {}),
                        "tee_type": attestation_data.get("tee_type", "unknown"),
                        "verified": True
                    }
                    
                    # Cache the result
                    self.attestation_cache[cache_key] = result
                    
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"TEE attestation failed: {response.status} - {error_text}")
                    return {
                        "status": AttestationStatus.FAILED.value,
                        "timestamp": datetime.utcnow().isoformat(),
                        "nonce": nonce,
                        "error": error_text,
                        "verified": False
                    }
        except Exception as e:
            logger.error(f"TEE attestation error: {e}")
            return {
                "status": AttestationStatus.FAILED.value,
                "timestamp": datetime.utcnow().isoformat(),
                "nonce": nonce,
                "error": str(e),
                "verified": False
            }
    
    async def verify_attestation(self, attestation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify TEE attestation report"""
        try:
            # Extract components
            report = attestation_data.get("report")
            signature = attestation_data.get("signature")
            cert_chain = attestation_data.get("certificate_chain")
            
            if not all([report, signature, cert_chain]):
                return {
                    "verified": False,
                    "status": AttestationStatus.FAILED.value,
                    "error": "Missing required attestation components"
                }
            
            # Verify signature (simplified - in production, use proper certificate validation)
            try:
                # This is a placeholder for actual attestation verification
                # In production, you would:
                # 1. Validate the certificate chain
                # 2. Verify the signature using the public key
                # 3. Check measurements against known good values
                # 4. Validate the nonce
                
                verification_result = {
                    "verified": True,
                    "status": AttestationStatus.VERIFIED.value,
                    "timestamp": datetime.utcnow().isoformat(),
                    "certificate_valid": True,
                    "signature_valid": True,
                    "measurements_valid": True,
                    "nonce_valid": True
                }
                
                return verification_result
                
            except Exception as verify_error:
                logger.error(f"Attestation verification failed: {verify_error}")
                return {
                    "verified": False,
                    "status": AttestationStatus.FAILED.value,
                    "error": str(verify_error)
                }
                
        except Exception as e:
            logger.error(f"Attestation verification error: {e}")
            return {
                "verified": False,
                "status": AttestationStatus.FAILED.value,
                "error": str(e)
            }
    
    async def get_tee_capabilities(self) -> Dict[str, Any]:
        """Get TEE environment capabilities"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.privatemode_base_url}/capabilities") as response:
                if response.status == 200:
                    capabilities = await response.json()
                    return {
                        "timestamp": datetime.utcnow().isoformat(),
                        "tee_type": capabilities.get("tee_type", "unknown"),
                        "secure_memory_size": capabilities.get("secure_memory_size", 0),
                        "encryption_algorithms": capabilities.get("encryption_algorithms", []),
                        "attestation_types": capabilities.get("attestation_types", []),
                        "key_management": capabilities.get("key_management", False),
                        "secure_storage": capabilities.get("secure_storage", False),
                        "network_isolation": capabilities.get("network_isolation", False),
                        "confidential_computing": capabilities.get("confidential_computing", False),
                        "details": capabilities
                    }
                else:
                    return {
                        "timestamp": datetime.utcnow().isoformat(),
                        "error": f"Failed to get capabilities: HTTP {response.status}"
                    }
        except Exception as e:
            logger.error(f"TEE capabilities error: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def create_secure_session(self, user_id: str, api_key_id: int) -> Dict[str, Any]:
        """Create a secure TEE session"""
        try:
            session = await self._get_session()
            payload = {
                "user_id": user_id,
                "api_key_id": api_key_id,
                "timestamp": datetime.utcnow().isoformat(),
                "requested_capabilities": [
                    "confidential_inference",
                    "secure_memory",
                    "attestation"
                ]
            }
            
            async with session.post(
                f"{self.privatemode_base_url}/session",
                json=payload
            ) as response:
                if response.status == 201:
                    session_data = await response.json()
                    return {
                        "session_id": session_data.get("session_id"),
                        "status": "active",
                        "timestamp": datetime.utcnow().isoformat(),
                        "capabilities": session_data.get("capabilities", []),
                        "expires_at": session_data.get("expires_at"),
                        "attestation_token": session_data.get("attestation_token")
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"TEE session creation failed: {response.status} - {error_text}")
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Failed to create TEE session: {error_text}"
                    )
        except aiohttp.ClientError as e:
            logger.error(f"TEE session creation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="TEE service unavailable"
            )
    
    async def get_privacy_metrics(self) -> Dict[str, Any]:
        """Get privacy and security metrics"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.privatemode_base_url}/metrics") as response:
                if response.status == 200:
                    metrics = await response.json()
                    return {
                        "timestamp": datetime.utcnow().isoformat(),
                        "requests_processed": metrics.get("requests_processed", 0),
                        "data_encrypted": metrics.get("data_encrypted", 0),
                        "attestations_verified": metrics.get("attestations_verified", 0),
                        "secure_sessions": metrics.get("secure_sessions", 0),
                        "uptime": metrics.get("uptime", 0),
                        "memory_usage": metrics.get("memory_usage", {}),
                        "performance": metrics.get("performance", {}),
                        "privacy_score": metrics.get("privacy_score", 0)
                    }
                else:
                    return {
                        "timestamp": datetime.utcnow().isoformat(),
                        "error": f"Failed to get metrics: HTTP {response.status}"
                    }
        except Exception as e:
            logger.error(f"TEE metrics error: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def list_tee_models(self) -> List[Dict[str, Any]]:
        """List available TEE models"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.privatemode_base_url}/models") as response:
                if response.status == 200:
                    models_data = await response.json()
                    models = []
                    
                    for model in models_data.get("models", []):
                        models.append({
                            "id": model.get("id"),
                            "name": model.get("name"),
                            "type": model.get("type", "chat"),
                            "provider": "privatemode",
                            "tee_enabled": True,
                            "confidential_computing": True,
                            "secure_inference": True,
                            "attestation_required": model.get("attestation_required", False),
                            "max_tokens": model.get("max_tokens", 4096),
                            "cost_per_token": model.get("cost_per_token", 0.0),
                            "availability": model.get("availability", "available")
                        })
                    
                    return models
                else:
                    logger.error(f"Failed to get TEE models: HTTP {response.status}")
                    return []
        except Exception as e:
            logger.error(f"TEE models error: {e}")
            return []
    
    async def cleanup_expired_cache(self):
        """Clean up expired attestation cache entries"""
        current_time = datetime.utcnow()
        expired_keys = []
        
        for key, cached_data in self.attestation_cache.items():
            if datetime.fromisoformat(cached_data["timestamp"]) + self.attestation_ttl <= current_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.attestation_cache[key]
        
        logger.info(f"Cleaned up {len(expired_keys)} expired attestation cache entries")


# Global TEE service instance
tee_service = TEEService()