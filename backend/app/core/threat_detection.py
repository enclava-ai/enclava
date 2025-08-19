"""
Core threat detection and security analysis for the platform
"""

import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from urllib.parse import unquote

from fastapi import Request
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ThreatLevel(Enum):
    """Threat severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuthLevel(Enum):
    """Authentication levels for rate limiting"""
    AUTHENTICATED = "authenticated"
    API_KEY = "api_key"
    PREMIUM = "premium"


@dataclass
class SecurityThreat:
    """Security threat detection result"""
    threat_type: str
    level: ThreatLevel
    confidence: float
    description: str
    source_ip: str
    user_agent: Optional[str] = None
    request_path: Optional[str] = None
    payload: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    mitigation: Optional[str] = None


@dataclass
class SecurityAnalysis:
    """Comprehensive security analysis result"""
    is_threat: bool
    threats: List[SecurityThreat]
    risk_score: float
    recommendations: List[str]
    auth_level: AuthLevel
    rate_limit_exceeded: bool
    should_block: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RateLimitInfo:
    """Rate limiting information"""
    auth_level: AuthLevel
    requests_per_minute: int
    requests_per_hour: int
    minute_limit: int
    hour_limit: int
    exceeded: bool


@dataclass
class AnomalyDetection:
    """Anomaly detection result"""
    is_anomaly: bool
    anomaly_type: str
    severity: float
    details: Dict[str, Any]
    baseline_value: Optional[float] = None
    current_value: Optional[float] = None


class ThreatDetectionService:
    """Core threat detection and security analysis service"""
    
    def __init__(self):
        self.name = "threat_detection"
        
        # Statistics
        self.stats = {
            'total_requests_analyzed': 0,
            'threats_detected': 0,
            'threats_blocked': 0,
            'anomalies_detected': 0,
            'rate_limits_exceeded': 0,
            'total_analysis_time': 0,
            'threat_types': defaultdict(int),
            'threat_levels': defaultdict(int),
            'attacking_ips': defaultdict(int)
        }
        
        # Threat detection patterns
        self.sql_injection_patterns = [
            r"(\bunion\b.*\bselect\b)",
            r"(\bselect\b.*\bfrom\b)",
            r"(\binsert\b.*\binto\b)",
            r"(\bupdate\b.*\bset\b)",
            r"(\bdelete\b.*\bfrom\b)",
            r"(\bdrop\b.*\btable\b)",
            r"(\bor\b.*\b1\s*=\s*1\b)",
            r"(\band\b.*\b1\s*=\s*1\b)",
            r"(\bexec\b.*\bxp_\w+)",
            r"(\bsp_\w+)",
            r"(\bsleep\b\s*\(\s*\d+\s*\))",
            r"(\bwaitfor\b.*\bdelay\b)",
            r"(\bbenchmark\b\s*\(\s*\d+)",
            r"(\bload_file\b\s*\()",
            r"(\binto\b.*\boutfile\b)"
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"<iframe[^>]*>.*?</iframe>",
            r"<object[^>]*>.*?</object>",
            r"<embed[^>]*>.*?</embed>",
            r"<link[^>]*>",
            r"<meta[^>]*>",
            r"javascript:",
            r"vbscript:",
            r"on\w+\s*=",
            r"style\s*=.*expression",
            r"style\s*=.*javascript"
        ]
        
        self.path_traversal_patterns = [
            r"\.\.\/",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e%5c",
            r"..%2f",
            r"..%5c",
            r"%252e%252e%252f",
            r"%252e%252e%255c"
        ]
        
        self.command_injection_patterns = [
            r";\s*cat\s+",
            r";\s*ls\s+",
            r";\s*pwd\s*",
            r";\s*whoami\s*",
            r";\s*id\s*",
            r";\s*uname\s*",
            r";\s*ps\s+",
            r";\s*netstat\s+",
            r";\s*wget\s+",
            r";\s*curl\s+",
            r"\|\s*cat\s+",
            r"\|\s*ls\s+",
            r"&&\s*cat\s+",
            r"&&\s*ls\s+"
        ]
        
        self.suspicious_ua_patterns = [
            r"sqlmap",
            r"nikto",
            r"nmap",
            r"masscan",
            r"zap",
            r"burp",
            r"w3af",
            r"acunetix",
            r"nessus",
            r"openvas",
            r"metasploit"
        ]
        
        # Rate limiting tracking - separate by auth level (excluding unauthenticated since they're blocked)
        self.rate_limits = {
            AuthLevel.AUTHENTICATED: defaultdict(lambda: {'minute': deque(maxlen=60), 'hour': deque(maxlen=3600)}),
            AuthLevel.API_KEY: defaultdict(lambda: {'minute': deque(maxlen=60), 'hour': deque(maxlen=3600)}),
            AuthLevel.PREMIUM: defaultdict(lambda: {'minute': deque(maxlen=60), 'hour': deque(maxlen=3600)})
        }
        
        # Anomaly detection
        self.request_history = deque(maxlen=1000)
        self.ip_history = defaultdict(lambda: deque(maxlen=100))
        self.endpoint_history = defaultdict(lambda: deque(maxlen=100))
        
        # Blocked and allowed IPs
        self.blocked_ips = set(settings.API_BLOCKED_IPS)
        self.allowed_ips = set(settings.API_ALLOWED_IPS) if settings.API_ALLOWED_IPS else None
        
        # IP reputation cache
        self.ip_reputation_cache = {}
        self.cache_expiry = {}
        
        # Compile patterns for performance
        self._compile_patterns()
        
        logger.info(f"ThreatDetectionService initialized with {len(self.sql_injection_patterns)} SQL patterns, "
                   f"{len(self.xss_patterns)} XSS patterns, rate limiting enabled: {settings.API_RATE_LIMITING_ENABLED}")
    
    def _compile_patterns(self):
        """Compile regex patterns for better performance"""
        try:
            self.compiled_sql_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.sql_injection_patterns]
            self.compiled_xss_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.xss_patterns]
            self.compiled_path_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.path_traversal_patterns]
            self.compiled_cmd_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.command_injection_patterns]
            self.compiled_ua_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.suspicious_ua_patterns]
        except re.error as e:
            logger.error(f"Failed to compile security patterns: {e}")
            # Fallback to empty lists to prevent crashes
            self.compiled_sql_patterns = []
            self.compiled_xss_patterns = []
            self.compiled_path_patterns = []
            self.compiled_cmd_patterns = []
            self.compiled_ua_patterns = []
    
    def determine_auth_level(self, request: Request, user_context: Optional[Dict] = None) -> AuthLevel:
        """Determine authentication level for rate limiting"""
        # Check if request has API key authentication
        if hasattr(request.state, 'api_key_context') and request.state.api_key_context:
            api_key = request.state.api_key_context.get('api_key')
            if api_key and hasattr(api_key, 'tier'):
                # Check for premium tier
                if api_key.tier in ['premium', 'enterprise']:
                    return AuthLevel.PREMIUM
            return AuthLevel.API_KEY
        
        # Check for JWT authentication
        if user_context or hasattr(request.state, 'user'):
            return AuthLevel.AUTHENTICATED
        
        # Check Authorization header for API key
        auth_header = request.headers.get("Authorization", "")
        api_key_header = request.headers.get("X-API-Key", "")
        if auth_header.startswith("Bearer ") or api_key_header:
            return AuthLevel.API_KEY
        
        # Default to authenticated since unauthenticated requests are blocked at middleware
        return AuthLevel.AUTHENTICATED
    
    def get_rate_limits(self, auth_level: AuthLevel) -> Tuple[int, int]:
        """Get rate limits for authentication level"""
        if not settings.API_RATE_LIMITING_ENABLED:
            return float('inf'), float('inf')
        
        if auth_level == AuthLevel.AUTHENTICATED:
            return (settings.API_RATE_LIMIT_AUTHENTICATED_PER_MINUTE, settings.API_RATE_LIMIT_AUTHENTICATED_PER_HOUR)
        elif auth_level == AuthLevel.API_KEY:
            return (settings.API_RATE_LIMIT_API_KEY_PER_MINUTE, settings.API_RATE_LIMIT_API_KEY_PER_HOUR)
        elif auth_level == AuthLevel.PREMIUM:
            return (settings.API_RATE_LIMIT_PREMIUM_PER_MINUTE, settings.API_RATE_LIMIT_PREMIUM_PER_HOUR)
        else:
            # Fallback to authenticated limits
            return (settings.API_RATE_LIMIT_AUTHENTICATED_PER_MINUTE, settings.API_RATE_LIMIT_AUTHENTICATED_PER_HOUR)
    
    def check_rate_limit(self, client_ip: str, auth_level: AuthLevel) -> RateLimitInfo:
        """Check if request exceeds rate limits"""
        minute_limit, hour_limit = self.get_rate_limits(auth_level)
        current_time = time.time()
        
        # Get or create tracking for this auth level
        if auth_level not in self.rate_limits:
            # This shouldn't happen, but handle gracefully
            return RateLimitInfo(
                auth_level=auth_level,
                requests_per_minute=0,
                requests_per_hour=0,
                minute_limit=minute_limit,
                hour_limit=hour_limit,
                exceeded=False
            )
        
        ip_limits = self.rate_limits[auth_level][client_ip]
        
        # Clean old entries
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        
        while ip_limits['minute'] and ip_limits['minute'][0] < minute_ago:
            ip_limits['minute'].popleft()
        
        while ip_limits['hour'] and ip_limits['hour'][0] < hour_ago:
            ip_limits['hour'].popleft()
        
        # Check current counts
        requests_per_minute = len(ip_limits['minute'])
        requests_per_hour = len(ip_limits['hour'])
        
        # Check if limits exceeded
        exceeded = (requests_per_minute >= minute_limit) or (requests_per_hour >= hour_limit)
        
        # Add current request to tracking
        if not exceeded:
            ip_limits['minute'].append(current_time)
            ip_limits['hour'].append(current_time)
        
        return RateLimitInfo(
            auth_level=auth_level,
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            minute_limit=minute_limit,
            hour_limit=hour_limit,
            exceeded=exceeded
        )
    
    async def analyze_request(self, request: Request, user_context: Optional[Dict] = None) -> SecurityAnalysis:
        """Perform comprehensive security analysis on a request"""
        start_time = time.time()
        
        try:
            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "")
            path = str(request.url.path)
            method = request.method
            
            # Determine authentication level
            auth_level = self.determine_auth_level(request, user_context)
            
            # Check IP allowlist/blocklist first
            if self.allowed_ips and client_ip not in self.allowed_ips:
                threat = SecurityThreat(
                    threat_type="ip_not_allowed",
                    level=ThreatLevel.HIGH,
                    confidence=1.0,
                    description=f"IP {client_ip} not in allowlist",
                    source_ip=client_ip,
                    mitigation="Add IP to allowlist or remove IP restrictions"
                )
                return SecurityAnalysis(
                    is_threat=True,
                    threats=[threat],
                    risk_score=1.0,
                    recommendations=["Block request immediately"],
                    auth_level=auth_level,
                    rate_limit_exceeded=False,
                    should_block=True
                )
            
            if client_ip in self.blocked_ips:
                threat = SecurityThreat(
                    threat_type="ip_blocked",
                    level=ThreatLevel.CRITICAL,
                    confidence=1.0,
                    description=f"IP {client_ip} is blocked",
                    source_ip=client_ip,
                    mitigation="Remove IP from blocklist if legitimate"
                )
                return SecurityAnalysis(
                    is_threat=True,
                    threats=[threat],
                    risk_score=1.0,
                    recommendations=["Block request immediately"],
                    auth_level=auth_level,
                    rate_limit_exceeded=False,
                    should_block=True
                )
            
            # Check rate limiting
            rate_limit_info = self.check_rate_limit(client_ip, auth_level)
            if rate_limit_info.exceeded:
                self.stats['rate_limits_exceeded'] += 1
                threat = SecurityThreat(
                    threat_type="rate_limit_exceeded",
                    level=ThreatLevel.MEDIUM,
                    confidence=0.9,
                    description=f"Rate limit exceeded for {auth_level.value}: {rate_limit_info.requests_per_minute}/min, {rate_limit_info.requests_per_hour}/hr",
                    source_ip=client_ip,
                    mitigation=f"Implement rate limiting, current limits: {rate_limit_info.minute_limit}/min, {rate_limit_info.hour_limit}/hr"
                )
                return SecurityAnalysis(
                    is_threat=True,
                    threats=[threat],
                    risk_score=0.7,
                    recommendations=[f"Rate limit exceeded for {auth_level.value} user"],
                    auth_level=auth_level,
                    rate_limit_exceeded=True,
                    should_block=True
                )
            
            # Skip threat detection if disabled
            if not settings.API_THREAT_DETECTION_ENABLED:
                return SecurityAnalysis(
                    is_threat=False,
                    threats=[],
                    risk_score=0.0,
                    recommendations=[],
                    auth_level=auth_level,
                    rate_limit_exceeded=False,
                    should_block=False
                )
            
            # Collect request data for threat analysis
            query_params = str(request.query_params)
            headers = dict(request.headers)
            
            # Try to get body content safely
            body_content = ""
            try:
                if hasattr(request, '_body') and request._body:
                    body_content = request._body.decode() if isinstance(request._body, bytes) else str(request._body)
            except:
                pass
            
            threats = []
            
            # Analyze for various threats
            threats.extend(await self._detect_sql_injection(query_params, body_content, path, client_ip))
            threats.extend(await self._detect_xss(query_params, body_content, headers, client_ip))
            threats.extend(await self._detect_path_traversal(path, query_params, client_ip))
            threats.extend(await self._detect_command_injection(query_params, body_content, client_ip))
            threats.extend(await self._detect_suspicious_patterns(headers, user_agent, path, client_ip))
            
            # Anomaly detection if enabled
            if settings.API_ANOMALY_DETECTION_ENABLED:
                anomaly = await self._detect_anomalies(client_ip, path, method, len(body_content))
                if anomaly.is_anomaly and anomaly.severity > settings.API_SECURITY_ANOMALY_THRESHOLD:
                    threat = SecurityThreat(
                        threat_type=f"anomaly_{anomaly.anomaly_type}",
                        level=ThreatLevel.MEDIUM if anomaly.severity > 0.7 else ThreatLevel.LOW,
                        confidence=anomaly.severity,
                        description=f"Anomalous behavior detected: {anomaly.details}",
                        source_ip=client_ip,
                        user_agent=user_agent,
                        request_path=path
                    )
                    threats.append(threat)
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(threats)
            
            # Determine if request should be blocked
            should_block = risk_score >= settings.API_SECURITY_RISK_THRESHOLD
            
            # Generate recommendations
            recommendations = self._generate_recommendations(threats, risk_score, auth_level)
            
            # Update statistics
            self._update_stats(threats, time.time() - start_time)
            
            return SecurityAnalysis(
                is_threat=len(threats) > 0,
                threats=threats,
                risk_score=risk_score,
                recommendations=recommendations,
                auth_level=auth_level,
                rate_limit_exceeded=False,
                should_block=should_block
            )
            
        except Exception as e:
            logger.error(f"Error in threat analysis: {e}")
            return SecurityAnalysis(
                is_threat=False,
                threats=[],
                risk_score=0.0,
                recommendations=["Error occurred during security analysis"],
                auth_level=AuthLevel.AUTHENTICATED,
                rate_limit_exceeded=False,
                should_block=False
            )
    
    async def _detect_sql_injection(self, query_params: str, body_content: str, path: str, client_ip: str) -> List[SecurityThreat]:
        """Detect SQL injection attempts"""
        threats = []
        content_to_check = f"{query_params} {body_content} {path}".lower()
        
        for pattern in self.compiled_sql_patterns:
            if pattern.search(content_to_check):
                threat = SecurityThreat(
                    threat_type="sql_injection",
                    level=ThreatLevel.HIGH,
                    confidence=0.85,
                    description="Potential SQL injection attempt detected",
                    source_ip=client_ip,
                    payload=pattern.pattern,
                    mitigation="Block request, sanitize input, use parameterized queries"
                )
                threats.append(threat)
                break  # Don't duplicate for multiple patterns
        
        return threats
    
    async def _detect_xss(self, query_params: str, body_content: str, headers: dict, client_ip: str) -> List[SecurityThreat]:
        """Detect XSS attempts"""
        threats = []
        content_to_check = f"{query_params} {body_content}".lower()
        
        # Check headers for XSS
        for header_name, header_value in headers.items():
            content_to_check += f" {header_value}".lower()
        
        for pattern in self.compiled_xss_patterns:
            if pattern.search(content_to_check):
                threat = SecurityThreat(
                    threat_type="xss",
                    level=ThreatLevel.HIGH,
                    confidence=0.80,
                    description="Potential XSS attack detected",
                    source_ip=client_ip,
                    payload=pattern.pattern,
                    mitigation="Block request, sanitize input, implement CSP headers"
                )
                threats.append(threat)
                break
        
        return threats
    
    async def _detect_path_traversal(self, path: str, query_params: str, client_ip: str) -> List[SecurityThreat]:
        """Detect path traversal attempts"""
        threats = []
        content_to_check = f"{path} {query_params}".lower()
        decoded_content = unquote(content_to_check)
        
        for pattern in self.compiled_path_patterns:
            if pattern.search(content_to_check) or pattern.search(decoded_content):
                threat = SecurityThreat(
                    threat_type="path_traversal",
                    level=ThreatLevel.HIGH,
                    confidence=0.90,
                    description="Path traversal attempt detected",
                    source_ip=client_ip,
                    request_path=path,
                    mitigation="Block request, validate file paths, implement access controls"
                )
                threats.append(threat)
                break
        
        return threats
    
    async def _detect_command_injection(self, query_params: str, body_content: str, client_ip: str) -> List[SecurityThreat]:
        """Detect command injection attempts"""
        threats = []
        content_to_check = f"{query_params} {body_content}".lower()
        
        for pattern in self.compiled_cmd_patterns:
            if pattern.search(content_to_check):
                threat = SecurityThreat(
                    threat_type="command_injection",
                    level=ThreatLevel.CRITICAL,
                    confidence=0.95,
                    description="Command injection attempt detected",
                    source_ip=client_ip,
                    payload=pattern.pattern,
                    mitigation="Block request immediately, sanitize input, disable shell execution"
                )
                threats.append(threat)
                break
        
        return threats
    
    async def _detect_suspicious_patterns(self, headers: dict, user_agent: str, path: str, client_ip: str) -> List[SecurityThreat]:
        """Detect suspicious patterns in headers and user agent"""
        threats = []
        
        # Check for suspicious user agents
        ua_lower = user_agent.lower()
        for pattern in self.compiled_ua_patterns:
            if pattern.search(ua_lower):
                threat = SecurityThreat(
                    threat_type="suspicious_user_agent",
                    level=ThreatLevel.HIGH,
                    confidence=0.85,
                    description=f"Suspicious user agent detected: {pattern.pattern}",
                    source_ip=client_ip,
                    user_agent=user_agent,
                    mitigation="Block request, monitor IP for further activity"
                )
                threats.append(threat)
                break
        
        # Check for suspicious headers
        if "x-forwarded-for" in headers and "x-real-ip" in headers:
            # Potential header manipulation
            threat = SecurityThreat(
                threat_type="header_manipulation",
                level=ThreatLevel.LOW,
                confidence=0.30,
                description="Potential IP header manipulation detected",
                source_ip=client_ip,
                mitigation="Validate proxy headers, implement IP whitelisting"
            )
            threats.append(threat)
        
        return threats
    
    async def _detect_anomalies(self, client_ip: str, path: str, method: str, body_size: int) -> AnomalyDetection:
        """Detect anomalous behavior patterns"""
        try:
            # Request size anomaly
            max_size = settings.API_MAX_REQUEST_BODY_SIZE
            if body_size > max_size:
                return AnomalyDetection(
                    is_anomaly=True,
                    anomaly_type="request_size",
                    severity=0.8,
                    details={"body_size": body_size, "threshold": max_size},
                    current_value=body_size,
                    baseline_value=max_size // 10
                )
            
            # Unusual endpoint access
            if path.startswith("/admin") or path.startswith("/api/admin"):
                return AnomalyDetection(
                    is_anomaly=True,
                    anomaly_type="sensitive_endpoint",
                    severity=0.6,
                    details={"path": path, "reason": "admin endpoint access"},
                    current_value=1.0,
                    baseline_value=0.0
                )
            
            # IP request frequency anomaly
            current_time = time.time()
            ip_requests = self.ip_history[client_ip]
            
            # Clean old entries (last 5 minutes)
            five_minutes_ago = current_time - 300
            while ip_requests and ip_requests[0] < five_minutes_ago:
                ip_requests.popleft()
            
            ip_requests.append(current_time)
            
            if len(ip_requests) > 100:  # More than 100 requests in 5 minutes
                return AnomalyDetection(
                    is_anomaly=True,
                    anomaly_type="request_frequency",
                    severity=0.7,
                    details={"requests_5min": len(ip_requests), "threshold": 100},
                    current_value=len(ip_requests),
                    baseline_value=10  # 10 requests baseline
                )
            
            return AnomalyDetection(
                is_anomaly=False,
                anomaly_type="none",
                severity=0.0,
                details={}
            )
            
        except Exception as e:
            logger.error(f"Error in anomaly detection: {e}")
            return AnomalyDetection(
                is_anomaly=False,
                anomaly_type="error",
                severity=0.0,
                details={"error": str(e)}
            )
    
    def _calculate_risk_score(self, threats: List[SecurityThreat]) -> float:
        """Calculate overall risk score based on threats"""
        if not threats:
            return 0.0
        
        score = 0.0
        for threat in threats:
            level_multiplier = {
                ThreatLevel.LOW: 0.25,
                ThreatLevel.MEDIUM: 0.5,
                ThreatLevel.HIGH: 0.75,
                ThreatLevel.CRITICAL: 1.0
            }
            score += threat.confidence * level_multiplier.get(threat.level, 0.5)
        
        # Normalize to 0-1 range
        return min(score / len(threats), 1.0)
    
    def _generate_recommendations(self, threats: List[SecurityThreat], risk_score: float, auth_level: AuthLevel) -> List[str]:
        """Generate security recommendations based on analysis"""
        recommendations = []
        
        if risk_score >= settings.API_SECURITY_RISK_THRESHOLD:
            recommendations.append("CRITICAL: Block this request immediately")
        elif risk_score >= settings.API_SECURITY_WARNING_THRESHOLD:
            recommendations.append("HIGH: Consider blocking or rate limiting this IP")
        elif risk_score > 0.4:
            recommendations.append("MEDIUM: Monitor this IP closely")
        
        threat_types = {threat.threat_type for threat in threats}
        
        if "sql_injection" in threat_types:
            recommendations.append("Implement parameterized queries and input validation")
        
        if "xss" in threat_types:
            recommendations.append("Implement Content Security Policy (CSP) headers")
        
        if "command_injection" in threat_types:
            recommendations.append("Disable shell execution and validate all inputs")
        
        if "path_traversal" in threat_types:
            recommendations.append("Implement proper file path validation and access controls")
        
        if "rate_limit_exceeded" in threat_types:
            recommendations.append(f"Rate limiting active for {auth_level.value} user")
        
        if not recommendations:
            recommendations.append("No immediate action required, continue monitoring")
        
        return recommendations
    
    def _update_stats(self, threats: List[SecurityThreat], analysis_time: float):
        """Update service statistics"""
        self.stats['total_requests_analyzed'] += 1
        self.stats['total_analysis_time'] += analysis_time
        
        if threats:
            self.stats['threats_detected'] += len(threats)
            for threat in threats:
                self.stats['threat_types'][threat.threat_type] += 1
                self.stats['threat_levels'][threat.level.value] += 1
                if threat.source_ip:
                    self.stats['attacking_ips'][threat.source_ip] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        avg_time = (self.stats['total_analysis_time'] / self.stats['total_requests_analyzed'] 
                   if self.stats['total_requests_analyzed'] > 0 else 0)
        
        # Get top attacking IPs
        top_ips = sorted(self.stats['attacking_ips'].items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "total_requests_analyzed": self.stats['total_requests_analyzed'],
            "threats_detected": self.stats['threats_detected'],
            "threats_blocked": self.stats['threats_blocked'],
            "anomalies_detected": self.stats['anomalies_detected'],
            "rate_limits_exceeded": self.stats['rate_limits_exceeded'],
            "avg_analysis_time": avg_time,
            "threat_types": dict(self.stats['threat_types']),
            "threat_levels": dict(self.stats['threat_levels']),
            "top_attacking_ips": top_ips,
            "security_enabled": settings.API_SECURITY_ENABLED,
            "threat_detection_enabled": settings.API_THREAT_DETECTION_ENABLED,
            "rate_limiting_enabled": settings.API_RATE_LIMITING_ENABLED
        }


# Global threat detection service instance
threat_detection_service = ThreatDetectionService()