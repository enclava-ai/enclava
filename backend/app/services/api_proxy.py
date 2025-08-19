"""
API Proxy with comprehensive security interceptors
"""
import json
import time
import re
from typing import Dict, List, Any, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import httpx
import yaml
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.services.api_key_auth import get_api_key_info
from app.services.budget_enforcement import check_budget_and_record_usage
from app.middleware.rate_limiting import rate_limiter
from app.utils.exceptions import ValidationError, AuthenticationError, RateLimitExceeded
from app.services.audit_service import create_audit_log

logger = get_logger(__name__)


class SecurityConfiguration:
    """Security configuration for API proxy"""
    
    def __init__(self):
        self.config = self._load_security_config()
    
    def _load_security_config(self) -> Dict[str, Any]:
        """Load security configuration"""
        return {
            "rate_limits": {
                "global": 10000,  # per hour
                "per_key": 1000,  # per hour
                "per_endpoint": {
                    "/api/llm/v1/chat/completions": 100,  # per minute
                    "/api/modules/v1/rag/search": 500,  # per hour
                }
            },
            "max_request_size": 10 * 1024 * 1024,  # 10MB
            "max_string_length": 50000,
            "timeout": 30,  # seconds
            "required_headers": ["X-API-Key"],
            "ip_whitelist_enabled": False,
            "ip_whitelist": [],
            "ip_blacklist": [],
            "forbidden_patterns": [
                "<script", "javascript:", "data:text/html", "vbscript:",
                "union select", "drop table", "insert into", "delete from"
            ],
            "audit": {
                "enabled": True,
                "include_request_body": False,
                "include_response_body": False,
                "sensitive_paths": ["/api/platform/v1/auth"]
            }
        }


class RequestValidator:
    """Validates API requests against schemas and security policies"""
    
    def __init__(self, config: SecurityConfiguration):
        self.config = config
        self.schemas = self._load_openapi_schemas()
    
    def _load_openapi_schemas(self) -> Dict[str, Any]:
        """Load OpenAPI schemas for validation"""
        # Would load actual OpenAPI schemas in production
        return {
            "POST /api/llm/v1/chat/completions": {
                "requestBody": {
                    "type": "object",
                    "required": ["model", "messages"],
                    "properties": {
                        "model": {"type": "string"},
                        "messages": {"type": "array"},
                        "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                        "max_tokens": {"type": "integer", "minimum": 1, "maximum": 32000}
                    }
                }
            },
            "POST /api/modules/v1/rag/search": {
                "requestBody": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string", "maxLength": 1000},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100}
                    }
                }
            }
        }
    
    async def validate(self, path: str, method: str, body: Dict, headers: Dict) -> Dict:
        """Validate request against schema and security policies"""
        
        # Check request size
        body_str = json.dumps(body)
        if len(body_str.encode()) > self.config.config["max_request_size"]:
            raise ValidationError(f"Request size exceeds maximum allowed")
        
        # Check required headers
        for header in self.config.config["required_headers"]:
            if header not in headers:
                raise ValidationError(f"Missing required header: {header}")
        
        # Validate against schema if available
        schema_key = f"{method.upper()} {path}"
        if schema_key in self.schemas:
            await self._validate_against_schema(body, self.schemas[schema_key])
        
        # Security validation
        self._validate_security_patterns(body)
        
        return body
    
    async def _validate_against_schema(self, body: Dict, schema: Dict):
        """Validate request body against OpenAPI schema"""
        request_schema = schema.get("requestBody", {})
        
        # Basic validation (would use proper JSON schema validator in production)
        if "required" in request_schema:
            for field in request_schema["required"]:
                if field not in body:
                    raise ValidationError(f"Missing required field: {field}")
        
        if "properties" in request_schema:
            for field, constraints in request_schema["properties"].items():
                if field in body:
                    await self._validate_field(field, body[field], constraints)
    
    async def _validate_field(self, field_name: str, value: Any, constraints: Dict):
        """Validate individual field against constraints"""
        field_type = constraints.get("type")
        
        if field_type == "string":
            if not isinstance(value, str):
                raise ValidationError(f"Field {field_name} must be a string")
            if "maxLength" in constraints and len(value) > constraints["maxLength"]:
                raise ValidationError(f"Field {field_name} exceeds maximum length")
        
        elif field_type == "integer":
            if not isinstance(value, int):
                raise ValidationError(f"Field {field_name} must be an integer")
            if "minimum" in constraints and value < constraints["minimum"]:
                raise ValidationError(f"Field {field_name} below minimum value")
            if "maximum" in constraints and value > constraints["maximum"]:
                raise ValidationError(f"Field {field_name} exceeds maximum value")
        
        elif field_type == "number":
            if not isinstance(value, (int, float)):
                raise ValidationError(f"Field {field_name} must be a number")
            if "minimum" in constraints and value < constraints["minimum"]:
                raise ValidationError(f"Field {field_name} below minimum value")
            if "maximum" in constraints and value > constraints["maximum"]:
                raise ValidationError(f"Field {field_name} exceeds maximum value")
    
    def _validate_security_patterns(self, body: Dict):
        """Check for forbidden security patterns"""
        body_str = json.dumps(body).lower()
        
        for pattern in self.config.config["forbidden_patterns"]:
            if pattern.lower() in body_str:
                raise ValidationError(f"Request contains forbidden pattern: {pattern}")


class APISecurityProxy:
    """Main API security proxy with interceptor pattern"""
    
    def __init__(self):
        self.config = SecurityConfiguration()
        self.request_validator = RequestValidator(self.config)
        
    async def proxy_request(self, request: Request, path: str) -> Response:
        """
        Main proxy method that implements the full interceptor pattern
        """
        start_time = time.time()
        api_key_info = None
        user_permissions = []
        
        try:
            # 1. Extract and validate API key
            api_key_info = await self._extract_and_validate_api_key(request)
            if api_key_info:
                user_permissions = api_key_info.get("permissions", [])
            
            # 2. IP validation (if enabled)
            await self._validate_ip_address(request)
            
            # 3. Rate limiting
            await self._check_rate_limits(request, path, api_key_info)
            
            # 4. Request validation and sanitization
            request_body = await self._get_request_body(request)
            validated_body = await self.request_validator.validate(
                path=path,
                method=request.method,
                body=request_body,
                headers=dict(request.headers)
            )
            
            # 5. Sanitize request
            sanitized_body = self._sanitize_request(validated_body)
            
            # 6. Budget checking (for LLM endpoints)
            if path.startswith("/api/llm/"):
                await self._check_budget_constraints(api_key_info, sanitized_body)
            
            # 7. Build proxy headers
            proxy_headers = self._build_proxy_headers(request, api_key_info)
            
            # 8. Log security event
            await self._log_security_event(
                request=request,
                path=path,
                api_key_info=api_key_info,
                sanitized_body=sanitized_body
            )
            
            # 9. Forward request to appropriate backend
            response = await self._forward_request(
                path=path,
                method=request.method,
                body=sanitized_body,
                headers=proxy_headers
            )
            
            # 10. Validate and sanitize response
            validated_response = await self._process_response(path, response)
            
            # 11. Record usage metrics
            await self._record_usage_metrics(
                api_key_info=api_key_info,
                path=path,
                duration=time.time() - start_time,
                success=True
            )
            
            return validated_response
            
        except Exception as e:
            # Error handling and logging
            await self._handle_error(
                request=request,
                path=path,
                api_key_info=api_key_info,
                error=e,
                duration=time.time() - start_time
            )
            
            # Return appropriate error response
            return await self._create_error_response(e)
    
    async def _extract_and_validate_api_key(self, request: Request) -> Optional[Dict[str, Any]]:
        """Extract and validate API key from request"""
        
        # Try different auth methods
        api_key = None
        
        # Bearer token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        
        # X-API-Key header
        elif request.headers.get("X-API-Key"):
            api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            raise AuthenticationError("Missing API key")
        
        # Validate API key
        api_key_info = await get_api_key_info(api_key)
        if not api_key_info:
            raise AuthenticationError("Invalid API key")
        
        if not api_key_info.get("is_active", False):
            raise AuthenticationError("API key is disabled")
        
        return api_key_info
    
    async def _validate_ip_address(self, request: Request):
        """Validate client IP address against whitelist/blacklist"""
        client_ip = request.client.host
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        config = self.config.config
        
        # Check blacklist
        if client_ip in config["ip_blacklist"]:
            raise AuthenticationError(f"IP address {client_ip} is blacklisted")
        
        # Check whitelist (if enabled)
        if config["ip_whitelist_enabled"] and client_ip not in config["ip_whitelist"]:
            raise AuthenticationError(f"IP address {client_ip} is not whitelisted")
    
    async def _check_rate_limits(self, request: Request, path: str, api_key_info: Optional[Dict]):
        """Check rate limits for the request"""
        client_ip = request.client.host
        api_key = api_key_info.get("key_prefix", "") if api_key_info else None
        
        # Use existing rate limiter
        if api_key:
            # API key-based rate limiting
            rate_limit_key = f"api_key:{api_key}"
            limit_per_minute = api_key_info.get("rate_limit_per_minute", 100)
            limit_per_hour = api_key_info.get("rate_limit_per_hour", 1000)
            
            # Check per-minute limit
            is_allowed_minute, _ = await rate_limiter.check_rate_limit(
                rate_limit_key, limit_per_minute, 60, "minute"
            )
            
            # Check per-hour limit
            is_allowed_hour, _ = await rate_limiter.check_rate_limit(
                rate_limit_key, limit_per_hour, 3600, "hour"
            )
            
            if not (is_allowed_minute and is_allowed_hour):
                raise RateLimitExceeded("API key rate limit exceeded")
        
        else:
            # IP-based rate limiting for unauthenticated requests
            rate_limit_key = f"ip:{client_ip}"
            
            is_allowed_minute, _ = await rate_limiter.check_rate_limit(
                rate_limit_key, 20, 60, "minute"
            )
            
            if not is_allowed_minute:
                raise RateLimitExceeded("IP rate limit exceeded")
    
    async def _get_request_body(self, request: Request) -> Dict[str, Any]:
        """Extract request body"""
        try:
            if request.method in ["POST", "PUT", "PATCH"]:
                return await request.json()
            else:
                return {}
        except Exception:
            return {}
    
    def _sanitize_request(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize request data"""
        def sanitize_value(value):
            if isinstance(value, str):
                # Remove forbidden patterns
                for pattern in self.config.config["forbidden_patterns"]:
                    value = re.sub(re.escape(pattern), "", value, flags=re.IGNORECASE)
                
                # Limit string length
                max_length = self.config.config["max_string_length"]
                if len(value) > max_length:
                    value = value[:max_length]
                    logger.warning(f"Truncated long string in request: {len(value)} chars")
                
                return value
            elif isinstance(value, dict):
                return {k: sanitize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [sanitize_value(item) for item in value]
            else:
                return value
        
        return sanitize_value(body)
    
    async def _check_budget_constraints(self, api_key_info: Dict, body: Dict):
        """Check budget constraints for LLM requests"""
        if not api_key_info:
            return
        
        # Estimate cost based on request
        estimated_cost = self._estimate_request_cost(body)
        
        # Check budget
        user_id = api_key_info.get("user_id")
        api_key_id = api_key_info.get("id")
        
        budget_ok = await check_budget_and_record_usage(
            user_id=user_id,
            api_key_id=api_key_id,
            estimated_cost=estimated_cost,
            actual_cost=0,  # Will be updated after response
            metadata={"endpoint": "llm_proxy", "model": body.get("model", "unknown")}
        )
        
        if not budget_ok:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Budget limit exceeded"
            )
    
    def _estimate_request_cost(self, body: Dict) -> float:
        """Estimate cost of LLM request"""
        # Rough estimation based on model and tokens
        model = body.get("model", "gpt-3.5-turbo")
        messages = body.get("messages", [])
        max_tokens = body.get("max_tokens", 1000)
        
        # Estimate input tokens
        input_text = " ".join([msg.get("content", "") for msg in messages if isinstance(msg, dict)])
        input_tokens = len(input_text.split()) * 1.3  # Rough approximation
        
        # Model pricing (simplified)
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},  # per 1K tokens
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125}
        }
        
        model_pricing = pricing.get(model, pricing["gpt-3.5-turbo"])
        
        estimated_cost = (
            (input_tokens / 1000) * model_pricing["input"] +
            (max_tokens / 1000) * model_pricing["output"]
        )
        
        return estimated_cost
    
    def _build_proxy_headers(self, request: Request, api_key_info: Optional[Dict]) -> Dict[str, str]:
        """Build headers for proxy request"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"ConfidentialEmpire-Proxy/1.0",
            "X-Forwarded-For": request.client.host,
            "X-Request-ID": f"req_{int(time.time() * 1000)}"
        }
        
        if api_key_info:
            headers["X-User-ID"] = str(api_key_info.get("user_id", ""))
            headers["X-API-Key-ID"] = str(api_key_info.get("id", ""))
        
        return headers
    
    async def _log_security_event(self, request: Request, path: str, api_key_info: Optional[Dict], sanitized_body: Dict):
        """Log security event for audit trail"""
        await create_audit_log(
            action=f"api_proxy_{request.method.lower()}",
            resource_type="api_endpoint",
            resource_id=path,
            user_id=api_key_info.get("user_id") if api_key_info else None,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("User-Agent", ""),
            metadata={
                "endpoint": path,
                "method": request.method,
                "api_key_id": api_key_info.get("id") if api_key_info else None,
                "request_size": len(json.dumps(sanitized_body))
            }
        )
    
    async def _forward_request(self, path: str, method: str, body: Dict, headers: Dict) -> Dict:
        """Forward request to appropriate backend service"""
        
        # Determine target service based on path
        if path.startswith("/api/llm/"):
            target_url = f"{settings.LITELLM_BASE_URL}{path}"
            target_headers = {**headers, "Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}"}
        elif path.startswith("/api/modules/"):
            # Route to module system
            return await self._route_to_module(path, method, body, headers)
        else:
            raise ValidationError(f"Unknown endpoint: {path}")
        
        # Make HTTP request to target service
        timeout = self.config.config["timeout"]
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                response = await client.get(target_url, headers=target_headers)
            elif method == "POST":
                response = await client.post(target_url, json=body, headers=target_headers)
            elif method == "PUT":
                response = await client.put(target_url, json=body, headers=target_headers)
            elif method == "DELETE":
                response = await client.delete(target_url, headers=target_headers)
            else:
                raise ValidationError(f"Unsupported HTTP method: {method}")
        
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        return response.json()
    
    async def _route_to_module(self, path: str, method: str, body: Dict, headers: Dict) -> Dict:
        """Route request to module system"""
        # Extract module name from path
        # e.g., /api/modules/v1/rag/search -> module: rag, action: search
        path_parts = path.strip("/").split("/")
        if len(path_parts) >= 4:
            module_name = path_parts[3]
            action = path_parts[4] if len(path_parts) > 4 else "execute"
        else:
            raise ValidationError("Invalid module path")
        
        # Import module manager
        from app.services.module_manager import module_manager
        
        if module_name not in module_manager.modules:
            raise ValidationError(f"Module not found: {module_name}")
        
        module = module_manager.modules[module_name]
        
        # Prepare context
        context = {
            "user_id": headers.get("X-User-ID"),
            "api_key_id": headers.get("X-API-Key-ID"),
            "ip_address": headers.get("X-Forwarded-For"),
            "user_permissions": []  # Would be populated from API key info
        }
        
        # Prepare request
        module_request = {
            "action": action,
            "method": method,
            **body
        }
        
        # Execute through module's interceptor chain
        if hasattr(module, 'execute_with_interceptors'):
            return await module.execute_with_interceptors(module_request, context)
        else:
            # Fallback for legacy modules
            if hasattr(module, action):
                return await getattr(module, action)(module_request)
            else:
                raise ValidationError(f"Action not supported: {action}")
    
    async def _process_response(self, path: str, response: Dict) -> JSONResponse:
        """Process and validate response"""
        # Add security headers
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
        }
        
        return JSONResponse(content=response, headers=headers)
    
    async def _record_usage_metrics(self, api_key_info: Optional[Dict], path: str, duration: float, success: bool):
        """Record usage metrics"""
        if api_key_info:
            # Record API key usage
            # This would update database metrics
            pass
    
    async def _handle_error(self, request: Request, path: str, api_key_info: Optional[Dict], error: Exception, duration: float):
        """Handle and log errors"""
        await create_audit_log(
            action=f"api_proxy_{request.method.lower()}",
            resource_type="api_endpoint",
            resource_id=path,
            user_id=api_key_info.get("user_id") if api_key_info else None,
            success=False,
            error_message=str(error),
            ip_address=request.client.host,
            user_agent=request.headers.get("User-Agent", ""),
            metadata={
                "endpoint": path,
                "method": request.method,
                "duration_ms": int(duration * 1000),
                "error_type": type(error).__name__
            }
        )
    
    async def _create_error_response(self, error: Exception) -> JSONResponse:
        """Create appropriate error response"""
        if isinstance(error, AuthenticationError):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "AUTHENTICATION_ERROR", "message": str(error)}
            )
        elif isinstance(error, ValidationError):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "VALIDATION_ERROR", "message": str(error)}
            )
        elif isinstance(error, RateLimitExceeded):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": "RATE_LIMIT_EXCEEDED", "message": str(error)}
            )
        elif isinstance(error, HTTPException):
            return JSONResponse(
                status_code=error.status_code,
                content={"error": "HTTP_ERROR", "message": error.detail}
            )
        else:
            logger.error(f"Unexpected error in API proxy: {error}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred"}
            )


# Global proxy instance
api_security_proxy = APISecurityProxy()