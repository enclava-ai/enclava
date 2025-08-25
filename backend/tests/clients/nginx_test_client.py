"""
Nginx reverse proxy test client for routing verification.
"""

import aiohttp
import asyncio
from typing import Dict, List, Optional, Any, Union
import json
import time


class NginxTestClient:
    """Test client for nginx reverse proxy routing"""
    
    def __init__(self, base_url: str = "http://localhost:3001"):
        self.base_url = base_url.rstrip('/')
        self.session_timeout = aiohttp.ClientTimeout(total=30)
    
    async def test_route(self, 
                        path: str, 
                        method: str = "GET",
                        headers: Optional[Dict[str, str]] = None,
                        data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Test a specific route through nginx"""
        url = f"{self.base_url}{path}"
        
        async with aiohttp.ClientSession(timeout=self.session_timeout) as session:
            start_time = time.time()
            
            try:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data if data else None
                ) as response:
                    end_time = time.time()
                    
                    # Read response
                    try:
                        response_data = await response.json()
                    except:
                        response_data = await response.text()
                    
                    return {
                        "url": url,
                        "method": method,
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "response_time": end_time - start_time,
                        "response_data": response_data,
                        "success": 200 <= response.status < 400
                    }
                    
            except asyncio.TimeoutError:
                return {
                    "url": url,
                    "method": method,
                    "error": "timeout",
                    "response_time": time.time() - start_time,
                    "success": False
                }
            except Exception as e:
                return {
                    "url": url,
                    "method": method,
                    "error": str(e),
                    "response_time": time.time() - start_time,
                    "success": False
                }
    
    async def test_public_api_routes(self) -> Dict[str, Any]:
        """Test public API routing (/api/v1/)"""
        routes_to_test = [
            {"path": "/api/v1/models", "method": "GET", "expected_auth": True},
            {"path": "/api/v1/chat/completions", "method": "POST", "expected_auth": True},
            {"path": "/api/v1/embeddings", "method": "POST", "expected_auth": True},
            {"path": "/api/v1/health", "method": "GET", "expected_auth": False},
        ]
        
        results = {}
        
        for route in routes_to_test:
            # Test without authentication
            result_unauth = await self.test_route(route["path"], route["method"])
            
            # Test with authentication
            headers = {"Authorization": "Bearer test-api-key"}
            result_auth = await self.test_route(route["path"], route["method"], headers)
            
            results[route["path"]] = {
                "unauthenticated": result_unauth,
                "authenticated": result_auth,
                "expects_auth": route["expected_auth"],
                "auth_working": (
                    result_unauth["status_code"] == 401 and 
                    result_auth["status_code"] != 401
                ) if route["expected_auth"] else True
            }
        
        return results
    
    async def test_internal_api_routes(self) -> Dict[str, Any]:
        """Test internal API routing (/api-internal/v1/)"""
        routes_to_test = [
            {"path": "/api-internal/v1/auth/me", "method": "GET"},
            {"path": "/api-internal/v1/auth/register", "method": "POST"},
            {"path": "/api-internal/v1/chatbot/list", "method": "GET"},
            {"path": "/api-internal/v1/rag/collections", "method": "GET"},
        ]
        
        results = {}
        
        for route in routes_to_test:
            # Test without authentication
            result_unauth = await self.test_route(route["path"], route["method"])
            
            # Test with JWT token
            headers = {"Authorization": "Bearer test-jwt-token"}
            result_auth = await self.test_route(route["path"], route["method"], headers)
            
            results[route["path"]] = {
                "unauthenticated": result_unauth,
                "authenticated": result_auth,
                "requires_auth": result_unauth["status_code"] == 401,
                "auth_working": result_unauth["status_code"] == 401 and result_auth["status_code"] != 401
            }
        
        return results
    
    async def test_frontend_routes(self) -> Dict[str, Any]:
        """Test frontend routing"""
        routes_to_test = [
            "/",
            "/dashboard", 
            "/chatbots",
            "/rag",
            "/settings",
            "/login"
        ]
        
        results = {}
        
        for path in routes_to_test:
            result = await self.test_route(path)
            results[path] = {
                "status_code": result["status_code"],
                "response_time": result["response_time"],
                "serves_html": "text/html" in result["headers"].get("content-type", ""),
                "success": result["success"]
            }
        
        return results
    
    async def test_cors_headers(self) -> Dict[str, Any]:
        """Test CORS headers configuration"""
        cors_tests = {}
        
        # Test preflight request
        cors_headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type"
        }
        
        preflight_result = await self.test_route("/api/v1/models", "OPTIONS", cors_headers)
        cors_tests["preflight"] = {
            "status_code": preflight_result["status_code"],
            "cors_headers": {
                k: v for k, v in preflight_result["headers"].items() 
                if k.lower().startswith("access-control")
            }
        }
        
        # Test actual CORS request
        request_headers = {"Origin": "http://localhost:3000"}
        cors_result = await self.test_route("/api/v1/models", "GET", request_headers)
        cors_tests["request"] = {
            "status_code": cors_result["status_code"], 
            "cors_headers": {
                k: v for k, v in cors_result["headers"].items()
                if k.lower().startswith("access-control")
            }
        }
        
        return cors_tests
    
    async def test_websocket_support(self) -> Dict[str, Any]:
        """Test WebSocket upgrade support for Next.js HMR"""
        ws_headers = {
            "Upgrade": "websocket",
            "Connection": "upgrade",
            "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
            "Sec-WebSocket-Version": "13"
        }
        
        result = await self.test_route("/", "GET", ws_headers)
        
        return {
            "status_code": result["status_code"],
            "upgrade_attempted": result["status_code"] in [101, 426],  # 101 = Switching Protocols, 426 = Upgrade Required
            "connection_header": result["headers"].get("connection", "").lower(),
            "upgrade_header": result["headers"].get("upgrade", "").lower()
        }
    
    async def test_health_endpoints(self) -> Dict[str, Any]:
        """Test health check endpoints"""
        health_endpoints = [
            "/health",
            "/api/v1/health", 
            "/test-status"
        ]
        
        results = {}
        
        for endpoint in health_endpoints:
            result = await self.test_route(endpoint)
            results[endpoint] = {
                "status_code": result["status_code"],
                "response_time": result["response_time"],
                "response_data": result["response_data"],
                "healthy": result["status_code"] == 200
            }
        
        return results
    
    async def test_static_file_handling(self) -> Dict[str, Any]:
        """Test static file serving and caching"""
        static_files = [
            "/_next/static/test.js",
            "/favicon.ico",
            "/static/test.css"
        ]
        
        results = {}
        
        for file_path in static_files:
            result = await self.test_route(file_path)
            results[file_path] = {
                "status_code": result["status_code"],
                "cache_control": result["headers"].get("cache-control"),
                "expires": result["headers"].get("expires"),
                "content_type": result["headers"].get("content-type"),
                "cached": "cache-control" in result["headers"] or "expires" in result["headers"]
            }
        
        return results
    
    async def test_error_handling(self) -> Dict[str, Any]:
        """Test nginx error handling"""
        error_tests = [
            {"path": "/nonexistent-page", "expected_status": 404},
            {"path": "/api/v1/nonexistent-endpoint", "expected_status": 404},
            {"path": "/api-internal/v1/nonexistent-endpoint", "expected_status": 404}
        ]
        
        results = {}
        
        for test in error_tests:
            result = await self.test_route(test["path"])
            results[test["path"]] = {
                "actual_status": result["status_code"],
                "expected_status": test["expected_status"],
                "correct_error": result["status_code"] == test["expected_status"],
                "response_data": result["response_data"]
            }
        
        return results
    
    async def test_load_balancing(self, num_requests: int = 50) -> Dict[str, Any]:
        """Test load balancing behavior with multiple requests"""
        async def make_request(request_id: int) -> Dict[str, Any]:
            result = await self.test_route("/health")
            return {
                "request_id": request_id,
                "status_code": result["status_code"],
                "response_time": result["response_time"],
                "success": result["success"]
            }
        
        tasks = [make_request(i) for i in range(num_requests)]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r["success"])
        avg_response_time = sum(r["response_time"] for r in results) / len(results)
        
        return {
            "total_requests": num_requests,
            "successful_requests": success_count,
            "failure_rate": (num_requests - success_count) / num_requests,
            "average_response_time": avg_response_time,
            "min_response_time": min(r["response_time"] for r in results),
            "max_response_time": max(r["response_time"] for r in results),
            "results": results
        }
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run all nginx tests"""
        return {
            "public_api_routes": await self.test_public_api_routes(),
            "internal_api_routes": await self.test_internal_api_routes(),
            "frontend_routes": await self.test_frontend_routes(),
            "cors_headers": await self.test_cors_headers(),
            "websocket_support": await self.test_websocket_support(),
            "health_endpoints": await self.test_health_endpoints(),
            "static_files": await self.test_static_file_handling(),
            "error_handling": await self.test_error_handling(),
            "load_test": await self.test_load_balancing(20)  # Smaller load test
        }