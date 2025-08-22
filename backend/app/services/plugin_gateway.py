"""
Plugin API Gateway
Handles authentication, routing, and security for plugin APIs
"""
import asyncio
import time
import jwt
from typing import Dict, Any, List, Optional, Tuple
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import aiohttp
from urllib.parse import urlparse
import hashlib
import hmac

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import verify_jwt_token, get_current_user
from app.models.plugin import Plugin, PluginConfiguration, PluginAuditLog
from app.models.api_key import APIKey
from app.models.user import User
from app.db.database import get_db
from app.services.plugin_sandbox import plugin_loader
from app.utils.exceptions import SecurityError, PluginError
from sqlalchemy.orm import Session


logger = get_logger("plugin.gateway")
security = HTTPBearer()


class PluginAuthenticationService:
    """Handles plugin authentication and authorization"""
    
    @staticmethod
    async def verify_plugin_token(token: str, db: Session) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Verify plugin authentication token"""
        try:
            # Decode JWT token
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET, 
                algorithms=["HS256"]
            )
            
            user_id = payload.get("sub")
            plugin_id = payload.get("plugin_id")
            
            if not user_id or not plugin_id:
                return None, None
            
            # Verify plugin exists and is active
            plugin = db.query(Plugin).filter(
                Plugin.id == plugin_id,
                Plugin.status == "enabled"
            ).first()
            
            if not plugin:
                return None, None
            
            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None, None
            
            return user_id, {
                "user": user,
                "plugin": plugin,
                "permissions": payload.get("permissions", [])
            }
            
        except jwt.InvalidTokenError:
            return None, None
    
    @staticmethod
    async def verify_api_key_access(api_key: str, plugin_id: str, db: Session) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Verify API key has access to plugin"""
        try:
            # Find API key
            api_key_obj = db.query(APIKey).filter(
                APIKey.key_hash == hashlib.sha256(api_key.encode()).hexdigest(),
                APIKey.is_active == True
            ).first()
            
            if not api_key_obj:
                return None, None
            
            # Check if API key has plugin access
            plugin = db.query(Plugin).filter(
                Plugin.id == plugin_id,
                Plugin.status == "enabled"
            ).first()
            
            if not plugin:
                return None, None
            
            # Verify plugin permissions for API key
            # TODO: Check plugin-specific permissions in API key scopes
            
            return api_key_obj.user_id, {
                "user": api_key_obj.user,
                "plugin": plugin,
                "api_key": api_key_obj,
                "permissions": ["api_access"]
            }
            
        except Exception as e:
            logger.error(f"API key verification failed: {e}")
            return None, None
    
    @staticmethod
    async def check_plugin_permissions(user_id: str, plugin_id: str, endpoint: str, 
                                     method: str, db: Session) -> bool:
        """Check if user has permission to access plugin endpoint"""
        try:
            # Get plugin configuration for user
            config = db.query(PluginConfiguration).filter(
                PluginConfiguration.user_id == user_id,
                PluginConfiguration.plugin_id == plugin_id,
                PluginConfiguration.is_active == True
            ).first()
            
            if not config:
                return False
            
            # Get plugin manifest to check endpoint permissions
            plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()
            if not plugin or not plugin.manifest_data:
                return False
            
            # Check endpoint permissions in manifest
            manifest = plugin.manifest_data
            api_endpoints = manifest.get("spec", {}).get("api_endpoints", [])
            
            for ep in api_endpoints:
                if ep.get("path") == endpoint and method in ep.get("methods", []):
                    return ep.get("auth_required", True)  # Default to requiring auth
            
            # If endpoint not found in manifest, deny access
            return False
            
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return False


class PluginAuditService:
    """Handles audit logging for plugin access"""
    
    @staticmethod
    async def log_plugin_access(
        plugin_id: str,
        user_id: Optional[str],
        api_key_id: Optional[str],
        endpoint: str,
        method: str,
        ip_address: str,
        user_agent: str,
        status_code: int,
        response_time_ms: float,
        db: Session
    ):
        """Log plugin API access for audit trail"""
        try:
            audit_log = PluginAuditLog(
                plugin_id=plugin_id,
                user_id=user_id,
                api_key_id=api_key_id,
                action="api_access",
                endpoint=endpoint,
                method=method,
                details={
                    "status_code": status_code,
                    "response_time_ms": response_time_ms,
                    "ip_address": ip_address,
                    "user_agent": user_agent
                }
            )
            
            db.add(audit_log)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log plugin access: {e}")
            db.rollback()


class PluginRateLimiter:
    """Rate limiting for plugin API access"""
    
    def __init__(self):
        self.user_requests: Dict[str, List[float]] = {}
        self.plugin_requests: Dict[str, List[float]] = {}
        
    def check_rate_limit(self, user_id: str, plugin_id: str, limits: Dict[str, int]) -> bool:
        """Check if request is within rate limits"""
        current_time = time.time()
        window_seconds = 60  # 1 minute window
        
        # Clean old requests
        self._clean_old_requests(current_time, window_seconds)
        
        # Check user rate limit
        user_key = f"user:{user_id}"
        user_limit = limits.get("user_requests_per_minute", 100)
        
        if user_key not in self.user_requests:
            self.user_requests[user_key] = []
        
        if len(self.user_requests[user_key]) >= user_limit:
            logger.warning(f"User {user_id} rate limit exceeded: {len(self.user_requests[user_key])}/{user_limit}")
            return False
        
        # Check plugin rate limit
        plugin_key = f"plugin:{plugin_id}"
        plugin_limit = limits.get("plugin_requests_per_minute", 200)
        
        if plugin_key not in self.plugin_requests:
            self.plugin_requests[plugin_key] = []
        
        if len(self.plugin_requests[plugin_key]) >= plugin_limit:
            logger.warning(f"Plugin {plugin_id} rate limit exceeded: {len(self.plugin_requests[plugin_key])}/{plugin_limit}")
            return False
        
        # Record requests
        self.user_requests[user_key].append(current_time)
        self.plugin_requests[plugin_key].append(current_time)
        
        return True
    
    def _clean_old_requests(self, current_time: float, window_seconds: int):
        """Remove requests older than window"""
        cutoff_time = current_time - window_seconds
        
        for key in self.user_requests:
            self.user_requests[key] = [
                req_time for req_time in self.user_requests[key] 
                if req_time > cutoff_time
            ]
        
        for key in self.plugin_requests:
            self.plugin_requests[key] = [
                req_time for req_time in self.plugin_requests[key] 
                if req_time > cutoff_time
            ]


class PluginGatewayMiddleware(BaseHTTPMiddleware):
    """Middleware for plugin API gateway"""
    
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.auth_service = PluginAuthenticationService()
        self.audit_service = PluginAuditService()
        self.rate_limiter = PluginRateLimiter()
    
    async def dispatch(self, request: Request, call_next):
        """Process plugin API requests"""
        start_time = time.time()
        
        # Check if this is a plugin API request
        if not request.url.path.startswith("/api/v1/plugins/"):
            return await call_next(request)
        
        # Extract plugin ID from path
        path_parts = request.url.path.split("/")
        if len(path_parts) < 5:
            return JSONResponse(
                status_code=404,
                content={"error": "Invalid plugin API path"}
            )
        
        plugin_id = path_parts[4]
        plugin_endpoint = "/" + "/".join(path_parts[5:]) if len(path_parts) > 5 else "/"
        
        # Get database session
        db = next(get_db())
        
        try:
            # Authenticate request
            auth_result = await self._authenticate_request(request, plugin_id, db)
            if not auth_result:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Authentication failed"}
                )
            
            user_id, auth_context = auth_result
            
            # Check permissions
            has_permission = await self.auth_service.check_plugin_permissions(
                user_id, plugin_id, plugin_endpoint, request.method, db
            )
            
            if not has_permission:
                return JSONResponse(
                    status_code=403,
                    content={"error": "Insufficient permissions"}
                )
            
            # Check rate limits
            rate_limits = {
                "user_requests_per_minute": 100,
                "plugin_requests_per_minute": 200
            }
            
            if not self.rate_limiter.check_rate_limit(user_id, plugin_id, rate_limits):
                return JSONResponse(
                    status_code=429,
                    content={"error": "Rate limit exceeded"}
                )
            
            # Add authentication context to request
            request.state.user_id = user_id
            request.state.plugin_id = plugin_id
            request.state.auth_context = auth_context
            request.state.plugin_endpoint = plugin_endpoint
            
            # Forward to plugin
            response = await self._forward_to_plugin(request, plugin_id, plugin_endpoint, call_next)
            
            # Log access
            response_time = (time.time() - start_time) * 1000
            await self.audit_service.log_plugin_access(
                plugin_id=plugin_id,
                user_id=user_id,
                api_key_id=auth_context.get("api_key", {}).get("id") if "api_key" in auth_context else None,
                endpoint=plugin_endpoint,
                method=request.method,
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent", ""),
                status_code=response.status_code,
                response_time_ms=response_time,
                db=db
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Plugin gateway error: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "Internal gateway error"}
            )
        finally:
            db.close()
    
    async def _authenticate_request(self, request: Request, plugin_id: str, db: Session) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Authenticate plugin API request"""
        
        # Check for Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header:
            return None
        
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            
            # Try JWT token first
            result = await self.auth_service.verify_plugin_token(token, db)
            if result[0]:
                return result
            
            # Try API key
            result = await self.auth_service.verify_api_key_access(token, plugin_id, db)
            if result[0]:
                return result
        
        return None
    
    async def _forward_to_plugin(self, request: Request, plugin_id: str, 
                               plugin_endpoint: str, call_next) -> Response:
        """Forward request to plugin and handle response"""
        
        # Check if plugin is loaded
        plugin_instance = plugin_loader.loaded_plugins.get(plugin_id)
        if not plugin_instance:
            return JSONResponse(
                status_code=503,
                content={"error": f"Plugin {plugin_id} not loaded"}
            )
        
        # Check sandbox resource usage
        sandbox = plugin_loader.get_plugin_sandbox(plugin_id)
        if sandbox:
            try:
                sandbox.check_resource_usage()
                sandbox.track_api_call()
            except Exception as e:
                return JSONResponse(
                    status_code=503,
                    content={"error": f"Plugin resource limit exceeded: {e}"}
                )
        
        # Add plugin context headers
        request.headers.__dict__["_list"].extend([
            (b"x-user-id", request.state.user_id.encode()),
            (b"x-plugin-id", plugin_id.encode()),
            (b"x-plugin-endpoint", plugin_endpoint.encode()),
            (b"x-real-ip", request.client.host.encode()),
        ])
        
        # Forward to plugin
        return await call_next(request)


class PluginAPIGateway:
    """Main plugin API gateway service"""
    
    def __init__(self):
        self.middleware = None
        self.app = None
        
    def init_app(self, app: FastAPI):
        """Initialize gateway with FastAPI app"""
        self.app = app
        self.middleware = PluginGatewayMiddleware(app)
        app.add_middleware(PluginGatewayMiddleware)
        
        # Add plugin management endpoints
        self._add_management_endpoints(app)
    
    def _add_management_endpoints(self, app: FastAPI):
        """Add plugin management endpoints"""
        
        @app.get("/api/v1/plugins")
        async def list_plugins(db: Session = Depends(get_db)):
            """List available plugins"""
            plugins = db.query(Plugin).filter(Plugin.status == "enabled").all()
            
            plugin_list = []
            for plugin in plugins:
                # Get runtime status
                plugin_instance = plugin_loader.loaded_plugins.get(plugin.id)
                loaded = plugin_instance is not None
                
                # Get resource stats if loaded
                resource_stats = {}
                if loaded:
                    resource_stats = plugin_loader.get_resource_stats(plugin.id)
                
                plugin_list.append({
                    "id": plugin.id,
                    "name": plugin.name,
                    "version": plugin.version,
                    "description": plugin.description,
                    "status": plugin.status,
                    "loaded": loaded,
                    "resource_usage": resource_stats,
                    "created_at": plugin.created_at.isoformat(),
                    "updated_at": plugin.updated_at.isoformat()
                })
            
            return {"plugins": plugin_list}
        
        @app.get("/api/v1/plugins/{plugin_id}")
        async def get_plugin(plugin_id: str, db: Session = Depends(get_db)):
            """Get plugin details"""
            plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()
            if not plugin:
                raise HTTPException(status_code=404, detail="Plugin not found")
            
            # Get runtime status
            plugin_instance = plugin_loader.loaded_plugins.get(plugin_id)
            loaded = plugin_instance is not None
            
            # Get resource stats if loaded
            resource_stats = {}
            health_status = {}
            if loaded:
                resource_stats = plugin_loader.get_resource_stats(plugin_id)
                health_status = await plugin_instance.health_check()
            
            return {
                "plugin": {
                    "id": plugin.id,
                    "name": plugin.name,
                    "version": plugin.version,
                    "description": plugin.description,
                    "status": plugin.status,
                    "manifest": plugin.manifest_data,
                    "loaded": loaded,
                    "resource_usage": resource_stats,
                    "health": health_status,
                    "created_at": plugin.created_at.isoformat(),
                    "updated_at": plugin.updated_at.isoformat()
                }
            }
        
        @app.post("/api/v1/plugins/{plugin_id}/load")
        async def load_plugin(plugin_id: str, db: Session = Depends(get_db)):
            """Load a plugin"""
            plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()
            if not plugin:
                raise HTTPException(status_code=404, detail="Plugin not found")
            
            if plugin.status != "enabled":
                raise HTTPException(status_code=400, detail="Plugin not enabled")
            
            # Check if already loaded
            if plugin_id in plugin_loader.loaded_plugins:
                raise HTTPException(status_code=400, detail="Plugin already loaded")
            
            try:
                # Load plugin
                plugin_dir = f"/plugins/{plugin_id}"
                plugin_token = "temp_token"  # TODO: Generate proper plugin token
                
                await plugin_loader.load_plugin_with_sandbox(plugin_dir, plugin_token)
                
                return {"status": "loaded", "plugin_id": plugin_id}
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to load plugin: {e}")
        
        @app.post("/api/v1/plugins/{plugin_id}/unload")
        async def unload_plugin(plugin_id: str):
            """Unload a plugin"""
            if plugin_id not in plugin_loader.loaded_plugins:
                raise HTTPException(status_code=404, detail="Plugin not loaded")
            
            try:
                success = await plugin_loader.unload_plugin(plugin_id)
                if success:
                    return {"status": "unloaded", "plugin_id": plugin_id}
                else:
                    raise HTTPException(status_code=500, detail="Failed to unload plugin")
                    
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to unload plugin: {e}")
        
        @app.get("/api/v1/plugins/{plugin_id}/health")
        async def get_plugin_health(plugin_id: str):
            """Get plugin health status"""
            plugin_instance = plugin_loader.loaded_plugins.get(plugin_id)
            if not plugin_instance:
                raise HTTPException(status_code=404, detail="Plugin not loaded")
            
            try:
                health = await plugin_instance.health_check()
                resource_stats = plugin_loader.get_resource_stats(plugin_id)
                
                return {
                    "health": health,
                    "resource_usage": resource_stats
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Health check failed: {e}")


# Global gateway instance
plugin_gateway = PluginAPIGateway()