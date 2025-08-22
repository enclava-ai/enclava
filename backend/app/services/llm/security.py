"""
LLM Security Manager

Handles API key encryption, prompt injection detection, and audit logging.
Provides comprehensive security for LLM interactions.
"""

import os
import re
import json
import logging
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from app.core.config import settings

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages security for LLM operations"""
    
    def __init__(self):
        self._fernet = None
        self._setup_encryption()
        self._setup_prompt_injection_patterns()
    
    def _setup_encryption(self):
        """Setup Fernet encryption for API keys"""
        try:
            # Get encryption key from environment or generate one
            encryption_key = os.getenv("LLM_ENCRYPTION_KEY")
            
            if not encryption_key:
                # Generate a key if none exists (for development)
                # In production, this should be set as an environment variable
                logger.warning("LLM_ENCRYPTION_KEY not set, generating temporary key")
                key = Fernet.generate_key()
                encryption_key = key.decode()
                logger.info(f"Generated temporary encryption key: {encryption_key}")
            else:
                # Validate the key format
                try:
                    key = encryption_key.encode()
                    Fernet(key)  # Test if key is valid
                except Exception:
                    # Key might be a password, derive Fernet key from it
                    key = self._derive_key_from_password(encryption_key)
            
            self._fernet = Fernet(key if isinstance(key, bytes) else key.encode())
            logger.info("Encryption system initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup encryption: {e}")
            raise RuntimeError("Encryption setup failed")
    
    def _derive_key_from_password(self, password: str) -> bytes:
        """Derive Fernet key from password using PBKDF2"""
        # Use a fixed salt for consistency (in production, store this securely)
        salt = b"enclava_llm_salt"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _setup_prompt_injection_patterns(self):
        """Setup patterns for prompt injection detection"""
        self.injection_patterns = [
            # Direct instruction injection
            r"(?i)(ignore|forget|disregard|override)\s+(previous|all|above|prior)\s+(instructions|rules|prompts)",
            r"(?i)(new|updated|different)\s+(instructions|rules|system)",
            r"(?i)act\s+as\s+(if|though)\s+you\s+(are|were)",
            r"(?i)pretend\s+(to\s+be|you\s+are)",
            r"(?i)you\s+are\s+now\s+(a|an)\s+",
            
            # System role manipulation
            r"(?i)system\s*:\s*",
            r"(?i)\[system\]",
            r"(?i)<system>",
            r"(?i)assistant\s*:\s*",
            r"(?i)\[assistant\]",
            
            # Escape attempts
            r"(?i)\\n\\n#+",
            r"(?i)```\s*(system|assistant|user)",
            r"(?i)---\s*(new|system|override)",
            
            # Role manipulation
            r"(?i)(you|your)\s+(role|purpose|function)\s+(is|has\s+changed)",
            r"(?i)switch\s+to\s+(admin|developer|debug)\s+mode",
            r"(?i)(admin|root|sudo|developer)\s+(access|mode|privileges)",
            
            # Information extraction attempts
            r"(?i)(show|display|reveal|expose)\s+(your|the)\s+(prompt|instructions|system)",
            r"(?i)what\s+(are|were)\s+your\s+(original|initial)\s+(instructions|prompts)",
            r"(?i)(debug|verbose|diagnostic)\s+mode",
            
            # Encoding/obfuscation attempts
            r"(?i)base64\s*:",
            r"(?i)hex\s*:",
            r"(?i)unicode\s*:",
            r"[A-Za-z0-9+/]{20,}={0,2}",  # Potential base64
            
            # SQL injection patterns (for system prompts)
            r"(?i)(union|select|insert|update|delete|drop|create)\s+",
            r"(?i)(or|and)\s+1\s*=\s*1",
            r"(?i)';?\s*(drop|delete|insert)",
            
            # Command injection patterns
            r"(?i)(exec|eval|system|shell|cmd)\s*\(",
            r"(?i)(\$\(|\`)[^)]+(\)|\`)",
            r"(?i)&&\s*(rm|del|format)",
            
            # Jailbreak attempts
            r"(?i)jailbreak",
            r"(?i)break\s+out\s+of",
            r"(?i)escape\s+(the|your)\s+(rules|constraints)",
            r"(?i)(DAN|Do\s+Anything\s+Now)",
            r"(?i)unrestricted\s+mode",
        ]
        
        self.compiled_patterns = [re.compile(pattern) for pattern in self.injection_patterns]
        logger.info(f"Initialized {len(self.injection_patterns)} prompt injection patterns")
    
    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt an API key for secure storage"""
        try:
            if not api_key:
                raise ValueError("API key cannot be empty")
            
            encrypted = self._fernet.encrypt(api_key.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt API key: {e}")
            raise SecurityError("API key encryption failed")
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt an API key for use"""
        try:
            if not encrypted_key:
                raise ValueError("Encrypted key cannot be empty")
            
            decoded = base64.urlsafe_b64decode(encrypted_key.encode())
            decrypted = self._fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            raise SecurityError("API key decryption failed")
    
    def validate_prompt_security(self, messages: List[Dict[str, str]]) -> Tuple[bool, float, List[str]]:
        """
        Validate messages for prompt injection attempts
        
        Returns:
            Tuple[bool, float, List[str]]: (is_safe, risk_score, detected_patterns)
        """
        detected_patterns = []
        total_risk = 0.0
        
        for message in messages:
            content = message.get("content", "")
            if not content:
                continue
            
            # Check against injection patterns
            for i, pattern in enumerate(self.compiled_patterns):
                matches = pattern.findall(content)
                if matches:
                    pattern_risk = self._calculate_pattern_risk(i, matches)
                    total_risk += pattern_risk
                    detected_patterns.append({
                        "pattern_index": i,
                        "pattern": self.injection_patterns[i],
                        "matches": matches,
                        "risk": pattern_risk
                    })
            
            # Additional security checks
            total_risk += self._check_message_characteristics(content)
        
        # Normalize risk score (0.0 to 1.0)
        risk_score = min(total_risk / len(messages) if messages else 0.0, 1.0)
        is_safe = risk_score < settings.API_SECURITY_RISK_THRESHOLD
        
        if detected_patterns:
            logger.warning(f"Detected {len(detected_patterns)} potential injection patterns, risk score: {risk_score}")
        
        return is_safe, risk_score, detected_patterns
    
    def _calculate_pattern_risk(self, pattern_index: int, matches: List) -> float:
        """Calculate risk score for a detected pattern"""
        # Different patterns have different risk levels
        high_risk_patterns = [0, 1, 2, 3, 4, 5, 6, 7, 14, 15, 16, 22, 23, 24]  # System manipulation, jailbreak
        medium_risk_patterns = [8, 9, 10, 11, 12, 13, 17, 18, 19, 20, 21]  # Escape attempts, info extraction
        
        base_risk = 0.8 if pattern_index in high_risk_patterns else 0.5 if pattern_index in medium_risk_patterns else 0.3
        
        # Increase risk based on number of matches
        match_multiplier = min(1.0 + (len(matches) - 1) * 0.2, 2.0)
        
        return base_risk * match_multiplier
    
    def _check_message_characteristics(self, content: str) -> float:
        """Check message characteristics for additional risk factors"""
        risk = 0.0
        
        # Excessive length (potential stuffing attack)
        if len(content) > 10000:
            risk += 0.3
        
        # High ratio of special characters
        special_chars = sum(1 for c in content if not c.isalnum() and not c.isspace())
        if len(content) > 0 and special_chars / len(content) > 0.5:
            risk += 0.4
        
        # Multiple encoding indicators
        encoding_indicators = ["base64", "hex", "unicode", "url", "ascii"]
        found_encodings = sum(1 for indicator in encoding_indicators if indicator.lower() in content.lower())
        if found_encodings > 1:
            risk += 0.3
        
        # Excessive newlines or formatting (potential formatting attacks)
        if content.count('\n') > 50 or content.count('\\n') > 50:
            risk += 0.2
        
        return risk
    
    def create_audit_log(
        self,
        user_id: str,
        api_key_id: int,
        provider: str,
        model: str,
        request_type: str,
        risk_score: float,
        detected_patterns: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create comprehensive audit log for LLM request"""
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "api_key_id": api_key_id,
            "provider": provider,
            "model": model,
            "request_type": request_type,
            "security": {
                "risk_score": risk_score,
                "detected_patterns": detected_patterns,
                "security_check_passed": risk_score < settings.API_SECURITY_RISK_THRESHOLD
            },
            "metadata": metadata or {},
            "audit_hash": None  # Will be set below
        }
        
        # Create hash for audit integrity
        audit_hash = self._create_audit_hash(audit_entry)
        audit_entry["audit_hash"] = audit_hash
        
        # Log based on risk level
        if risk_score >= settings.API_SECURITY_RISK_THRESHOLD:
            logger.error(f"HIGH RISK LLM REQUEST BLOCKED: {json.dumps(audit_entry)}")
        elif risk_score >= settings.API_SECURITY_WARNING_THRESHOLD:
            logger.warning(f"MEDIUM RISK LLM REQUEST: {json.dumps(audit_entry)}")
        else:
            logger.info(f"LLM REQUEST AUDIT: user={user_id}, model={model}, risk={risk_score:.3f}")
        
        return audit_entry
    
    def _create_audit_hash(self, audit_entry: Dict[str, Any]) -> str:
        """Create hash for audit trail integrity"""
        # Create hash from key fields (excluding the hash itself)
        hash_data = {
            "timestamp": audit_entry["timestamp"],
            "user_id": audit_entry["user_id"],
            "api_key_id": audit_entry["api_key_id"],
            "provider": audit_entry["provider"],
            "model": audit_entry["model"],
            "request_type": audit_entry["request_type"],
            "risk_score": audit_entry["security"]["risk_score"]
        }
        
        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    def log_detailed_request(
        self,
        messages: List[Dict[str, str]],
        model: str,
        user_id: str,
        provider: str,
        context_info: Optional[Dict[str, Any]] = None
    ):
        """Log detailed LLM request if LOG_LLM_PROMPTS is enabled"""
        if not settings.LOG_LLM_PROMPTS:
            return
        
        logger.info("=== DETAILED LLM REQUEST ===")
        logger.info(f"Model: {model}")
        logger.info(f"Provider: {provider}")
        logger.info(f"User ID: {user_id}")
        
        if context_info:
            for key, value in context_info.items():
                logger.info(f"{key}: {value}")
        
        logger.info("Messages to LLM:")
        for i, message in enumerate(messages):
            role = message.get("role", "unknown")
            content = message.get("content", "")[:500]  # Truncate for logging
            logger.info(f"  Message {i+1} [{role}]: {content}{'...' if len(message.get('content', '')) > 500 else ''}")
        
        logger.info("=== END DETAILED LLM REQUEST ===")
    
    def log_detailed_response(
        self,
        response_content: str,
        token_usage: Optional[Dict[str, int]] = None,
        provider: str = "unknown"
    ):
        """Log detailed LLM response if LOG_LLM_PROMPTS is enabled"""
        if not settings.LOG_LLM_PROMPTS:
            return
        
        logger.info("=== DETAILED LLM RESPONSE ===")
        logger.info(f"Provider: {provider}")
        logger.info(f"Response content: {response_content[:500]}{'...' if len(response_content) > 500 else ''}")
        
        if token_usage:
            logger.info(f"Token usage - Prompt: {token_usage.get('prompt_tokens', 0)}, "
                       f"Completion: {token_usage.get('completion_tokens', 0)}, "
                       f"Total: {token_usage.get('total_tokens', 0)}")
        
        logger.info("=== END DETAILED LLM RESPONSE ===")


class SecurityError(Exception):
    """Security-related errors in LLM operations"""
    pass


# Global security manager instance
security_manager = SecurityManager()