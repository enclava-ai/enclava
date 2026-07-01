"""
Legacy threat-detection service.

This module provides a lightweight, deterministic detector used by older
security tests and integrations. It does not replace the current audit and
middleware security paths.
"""

from __future__ import annotations

import html
import inspect
import ipaddress
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

from app.models.security_event import SecurityEvent


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class _DefaultIPReputationService:
    def check_reputation(self, ip: str) -> Dict[str, Any]:
        return {
            "is_malicious": False,
            "threat_types": [],
            "confidence": 0.0,
            "last_seen": None,
        }


class ThreatDetectionService:
    """Pattern-based threat detector retained for compatibility."""

    def __init__(self, db_session: Any = None, redis_client: Any = None) -> None:
        self.db_session = db_session
        self.redis_client = redis_client
        self.ip_reputation_service = _DefaultIPReputationService()
        self._request_patterns: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def _normalize(self, content: str) -> str:
        decoded = content
        for _ in range(2):
            decoded = unquote(decoded)
        return html.unescape(decoded)

    async def analyze_content(self, content: str) -> Dict[str, Any]:
        if content is None:
            raise TypeError("content is required")

        payload_size = len(content)
        if not content.strip():
            return {
                "threat_detected": False,
                "threat_type": None,
                "risk_score": 0.0,
                "details": "No content",
                "payload_size": payload_size,
            }

        normalized = self._normalize(content)
        lowered = normalized.lower()

        checks = [
            self._detect_sql_injection(lowered),
            self._detect_xss(lowered),
            self._detect_command_injection(lowered),
            self._detect_path_traversal(lowered),
        ]
        detected = [check for check in checks if check["threat_detected"]]
        if detected:
            strongest = max(detected, key=lambda item: item["risk_score"])
            strongest["payload_size"] = payload_size
            return strongest

        return {
            "threat_detected": False,
            "threat_type": None,
            "risk_score": 0.0,
            "details": "No threats detected",
            "payload_size": payload_size,
        }

    def _detect_sql_injection(self, value: str) -> Dict[str, Any]:
        patterns = [
            r"'\s*or\s*'?\d+'?\s*=\s*'?\d+",
            r"\bor\s+1\s*=\s*1\b",
            r"\bunion\s+select\b",
            r";\s*(drop|delete|insert|update|exec)\b",
            r"\b(drop\s+table|delete\s+from|insert\s+into|xp_cmdshell)\b",
            r"\b(waitfor\s+delay|sleep\s*\(|extractvalue\s*\()\b",
            r"--|#",
        ]
        if any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns):
            advanced = any(
                token in value
                for token in [
                    "waitfor",
                    "sleep(",
                    "extractvalue",
                    "substring",
                    "xp_cmdshell",
                    "insert into",
                    "concat(",
                ]
            )
            return {
                "threat_detected": True,
                "threat_type": "sql_injection",
                "risk_score": 0.95 if advanced else 0.85,
                "details": "SQL injection pattern detected",
            }
        return {"threat_detected": False, "risk_score": 0.0}

    def _detect_xss(self, value: str) -> Dict[str, Any]:
        patterns = [
            r"<\s*script\b",
            r"on(?:error|load|focus)\s*=",
            r"javascript\s*:",
            r"<\s*(img|svg|iframe|body|input)\b[^>]*(on\w+\s*=|javascript\s*:)",
        ]
        if any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns):
            obfuscated = any(
                token in value for token in ["&#", "%3c", "fromcharcode", "<<"]
            )
            return {
                "threat_detected": True,
                "threat_type": "xss",
                "risk_score": 0.85 if obfuscated else 0.8,
                "details": "XSS/script pattern detected",
            }
        return {"threat_detected": False, "risk_score": 0.0}

    def _detect_command_injection(self, value: str) -> Dict[str, Any]:
        patterns = [
            r"(^|[;&|])\s*(ls|cat|rm|curl|wget|nc|whoami)\b",
            r"`[^`]+`",
            r"\$\([^)]*(cat|whoami|curl|wget|rm|ls)[^)]*\)",
            r"\b(cmd\s*/c|powershell(?:\.exe)?\b)",
            r"\bexecutionpolicy\s+bypass\b",
        ]
        if any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns):
            high = "powershell" in value or "executionpolicy" in value
            return {
                "threat_detected": True,
                "threat_type": "command_injection",
                "risk_score": 0.95 if high else 0.85,
                "details": "Command injection pattern detected",
            }
        return {"threat_detected": False, "risk_score": 0.0}

    def _detect_path_traversal(self, value: str) -> Dict[str, Any]:
        traversal_count = value.count("../") + value.count("..\\")
        sensitive = any(
            token in value for token in ["etc/passwd", "boot.ini", "system32"]
        )
        if traversal_count >= 2 or sensitive:
            return {
                "threat_detected": True,
                "threat_type": "path_traversal",
                "risk_score": 0.8 if sensitive else 0.7,
                "details": "Path traversal pattern detected",
            }
        return {"threat_detected": False, "risk_score": 0.0}

    def _is_private_network(self, ip: str) -> bool:
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return False
        private_networks = [
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
            ipaddress.ip_network("127.0.0.0/8"),
        ]
        return any(address in network for network in private_networks)

    async def check_ip_reputation(self, ip: str) -> Dict[str, Any]:
        if self._is_private_network(ip):
            return {
                "is_malicious": False,
                "threat_types": [],
                "confidence": 0,
                "notes": "Private/local IP range skipped",
            }
        try:
            return await _maybe_await(self.ip_reputation_service.check_reputation(ip))
        except Exception as exc:
            return {
                "is_malicious": False,
                "threat_types": [],
                "confidence": 0,
                "error": str(exc),
            }

    async def detect_rate_anomaly(
        self, client_ip: str, endpoint: str
    ) -> Dict[str, Any]:
        requests_per_minute = 0
        if self.redis_client is not None:
            requests_per_minute = int(
                await _maybe_await(self.redis_client.get(f"rpm:{client_ip}:{endpoint}"))
                or 0
            )
        detected = requests_per_minute >= 500
        return {
            "anomaly_detected": detected,
            "anomaly_type": "high_request_rate" if detected else None,
            "risk_score": 0.85 if detected else 0.0,
            "requests_per_minute": requests_per_minute,
        }

    async def detect_payload_anomaly(
        self, content: str, endpoint: str
    ) -> Dict[str, Any]:
        payload_size = len(content or "")
        detected = payload_size >= 1_000_000
        return {
            "anomaly_detected": detected,
            "anomaly_type": "large_payload" if detected else None,
            "risk_score": 0.65 if detected else 0.0,
            "payload_size": payload_size,
        }

    async def detect_user_agent_anomaly(self, user_agent: str) -> Dict[str, Any]:
        if not user_agent:
            return {
                "anomaly_detected": True,
                "anomaly_type": "empty_user_agent",
                "risk_score": 0.5,
            }
        lowered = user_agent.lower()
        if len(user_agent) > 512:
            return {
                "anomaly_detected": True,
                "anomaly_type": "abnormal_length",
                "risk_score": 0.6,
            }
        if any(tool in lowered for tool in ["sqlmap", "nikto", "dirb", "spider"]):
            return {
                "anomaly_detected": True,
                "anomaly_type": "suspicious_tool",
                "risk_score": 0.7,
            }
        return {"anomaly_detected": False, "anomaly_type": None, "risk_score": 0.0}

    async def track_request_pattern(
        self,
        client_ip: str,
        path: str,
        response_code: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._request_patterns[client_ip].append(
            {
                "path": path,
                "response_code": response_code,
                "metadata": metadata or {},
            }
        )

    async def analyze_request_patterns(self, client_ip: str) -> Dict[str, Any]:
        records = self._request_patterns.get(client_ip, [])
        failed_logins = [
            record
            for record in records
            if record["response_code"] == 401 or record["metadata"].get("failed_login")
        ]
        if len(failed_logins) >= 10:
            return {
                "pattern_detected": True,
                "pattern_type": "brute_force_login",
                "failed_attempts": len(failed_logins),
                "risk_score": 0.95,
            }

        not_found = [record for record in records if record["response_code"] == 404]
        if len(not_found) >= 8:
            return {
                "pattern_detected": True,
                "pattern_type": "directory_scanning",
                "request_count": len(records),
                "risk_score": 0.85,
            }

        return {
            "pattern_detected": False,
            "pattern_type": None,
            "request_count": len(records),
            "risk_score": 0.0,
        }

    async def analyze_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        detected_threats: List[str] = []
        scores: List[float] = []
        passed_checks = 0
        failed_checks = 0

        content_result = await self.analyze_content(request.get("body", ""))
        if content_result["threat_detected"]:
            detected_threats.append(content_result["threat_type"])
            scores.append(content_result["risk_score"])
            failed_checks += 1
        else:
            passed_checks += 1

        user_agent_result = await self.detect_user_agent_anomaly(
            request.get("headers", {}).get("User-Agent", "")
        )
        if user_agent_result["anomaly_detected"]:
            detected_threats.append(user_agent_result["anomaly_type"])
            scores.append(user_agent_result["risk_score"])
            failed_checks += 1
        else:
            passed_checks += 1

        reputation = await self.check_ip_reputation(request.get("client_ip", ""))
        if reputation.get("is_malicious"):
            detected_threats.append("malicious_ip")
            scores.append(float(reputation.get("confidence", 0.8)))
            failed_checks += 1
        else:
            passed_checks += 1

        overall_risk = max(scores) if scores else 0.0
        return {
            "threat_detected": bool(detected_threats),
            "overall_risk_score": overall_risk,
            "detected_threats": detected_threats,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
        }

    async def log_security_event(self, event_data: Dict[str, Any]) -> None:
        if self.db_session is None:
            return
        event = SecurityEvent(**event_data)
        self.db_session.add(event)
        await _maybe_await(self.db_session.commit())

    async def get_security_events(
        self, client_ip: Optional[str] = None, limit: int = 100
    ) -> List[SecurityEvent]:
        if self.db_session is None:
            return []
        query = self.db_session.query(SecurityEvent)
        if client_ip:
            query = query.filter(SecurityEvent.client_ip == client_ip)
        return query.order_by(SecurityEvent.timestamp.desc()).limit(limit).all()
