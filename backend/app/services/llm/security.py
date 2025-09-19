"""
LLM Security Manager

Handles prompt injection detection and audit logging.
Provides comprehensive security for LLM interactions.
"""

import os
import re
import json
import logging
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages security for LLM operations"""
    
    def __init__(self):
        self._setup_prompt_injection_patterns()
    
    
    def _setup_prompt_injection_patterns(self):
        """Setup patterns for prompt injection detection"""
        self.injection_patterns = [
            # Direct instruction injection
            r"(?i)(ignore|forget|disregard|override).{0,20}(instructions|rules|prompts)",
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
            r"(?i)\b[A-Za-z0-9+/]{40,}={0,2}\b",  # More specific base64 pattern (longer sequences)
            
            # SQL injection patterns (more specific to reduce false positives)
            r"(?i)(union\s+select|select\s+\*|insert\s+into|update\s+\w+\s+set|delete\s+from|drop\s+table|create\s+table)\s",
            r"(?i)(or|and)\s+\d+\s*=\s*\d+",
            r"(?i)';?\s*(drop\s+table|delete\s+from|insert\s+into)",
            
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
    
    
    def validate_prompt_security(self, messages: List[Dict[str, str]]) -> Tuple[bool, float, List[str]]:
        """
        Validate messages for prompt injection attempts

        Returns:
            Tuple[bool, float, List[str]]: (is_safe, risk_score, detected_patterns)
        """
        detected_patterns = []
        total_risk = 0.0

        # Check if this is a system/RAG request
        is_system_request = self._is_system_request(messages)

        for message in messages:
            content = message.get("content", "")
            if not content:
                continue

            # Check against injection patterns with context awareness
            for i, pattern in enumerate(self.compiled_patterns):
                matches = pattern.findall(content)
                if matches:
                    # Apply context-aware risk calculation
                    pattern_risk = self._calculate_pattern_risk(i, matches, message.get("role", "user"), is_system_request)
                    total_risk += pattern_risk
                    detected_patterns.append({
                        "pattern_index": i,
                        "pattern": self.injection_patterns[i],
                        "matches": matches,
                        "risk": pattern_risk
                    })

            # Additional security checks with context awareness
            total_risk += self._check_message_characteristics(content, message.get("role", "user"), is_system_request)

        # Normalize risk score (0.0 to 1.0)
        risk_score = min(total_risk / len(messages) if messages else 0.0, 1.0)
        # Never block - always return True for is_safe
        is_safe = True

        if detected_patterns:
            logger.info(f"Detected {len(detected_patterns)} potential injection patterns, risk score: {risk_score} (system_request: {is_system_request})")

        return is_safe, risk_score, detected_patterns
    
    def _calculate_pattern_risk(self, pattern_index: int, matches: List, role: str, is_system_request: bool) -> float:
        """Calculate risk score for a detected pattern with context awareness"""
        # Different patterns have different risk levels
        high_risk_patterns = [0, 1, 2, 3, 4, 5, 6, 7, 22, 23, 24]  # System manipulation, jailbreak
        medium_risk_patterns = [8, 9, 10, 11, 12, 13, 17, 18, 19, 20, 21]  # Escape attempts, info extraction

        # Base risk score
        base_risk = 0.8 if pattern_index in high_risk_patterns else 0.5 if pattern_index in medium_risk_patterns else 0.3

        # Apply context-specific risk reduction
        if is_system_request or role == "system":
            # Reduce risk for system messages and RAG content
            if pattern_index in [14, 15, 16]:  # Encoding patterns (base64, hex, unicode)
                base_risk *= 0.2  # Reduce encoding risk by 80% for system content
            elif pattern_index in [17, 18, 19]:  # SQL patterns
                base_risk *= 0.3  # Reduce SQL risk by 70% for system content
            else:
                base_risk *= 0.6  # Reduce other risks by 40% for system content

        # Increase risk based on number of matches, but cap it
        match_multiplier = min(1.0 + (len(matches) - 1) * 0.1, 1.5)  # Reduced multiplier

        return base_risk * match_multiplier
    
    def _check_message_characteristics(self, content: str, role: str, is_system_request: bool) -> float:
        """Check message characteristics for additional risk factors with context awareness"""
        risk = 0.0

        # Excessive length (potential stuffing attack) - less restrictive for system content
        length_threshold = 50000 if is_system_request else 10000  # Much higher threshold for system content
        if len(content) > length_threshold:
            risk += 0.1 if is_system_request else 0.3

        # High ratio of special characters - more lenient for system content
        special_chars = sum(1 for c in content if not c.isalnum() and not c.isspace())
        if len(content) > 0:
            char_ratio = special_chars / len(content)
            threshold = 0.8 if is_system_request else 0.5
            if char_ratio > threshold:
                risk += 0.2 if is_system_request else 0.4

        # Multiple encoding indicators - reduced risk for system content
        encoding_indicators = ["base64", "hex", "unicode", "url", "ascii"]
        found_encodings = sum(1 for indicator in encoding_indicators if indicator.lower() in content.lower())
        if found_encodings > 1:
            risk += 0.1 if is_system_request else 0.3

        # Excessive newlines or formatting - more lenient for system content
        newline_threshold = 200 if is_system_request else 50
        if content.count('\n') > newline_threshold or content.count('\\n') > newline_threshold:
            risk += 0.1 if is_system_request else 0.2

        return risk

    def _is_system_request(self, messages: List[Dict[str, str]]) -> bool:
        """Determine if this is a system/RAG request"""
        if not messages:
            return False

        # Check for system messages
        for message in messages:
            if message.get("role") == "system":
                return True

        # Check message content for RAG indicators
        for message in messages:
            content = message.get("content", "")
            if ("document:" in content.lower() or
                "context:" in content.lower() or
                "source:" in content.lower() or
                "retrieved:" in content.lower() or
                "citation:" in content.lower() or
                "reference:" in content.lower()):
                return True

        return False

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
        
        # Log based on risk level (never block, only log)
        if risk_score >= settings.API_SECURITY_RISK_THRESHOLD:
            logger.warning(f"HIGH RISK LLM REQUEST DETECTED (NOT BLOCKED): {json.dumps(audit_entry)}")
        elif risk_score >= settings.API_SECURITY_WARNING_THRESHOLD:
            logger.info(f"MEDIUM RISK LLM REQUEST: {json.dumps(audit_entry)}")
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