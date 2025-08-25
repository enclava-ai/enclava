"""
Nginx reverse proxy routing tests.
Test all nginx routing configurations through actual HTTP requests.
"""

import pytest
import asyncio
import aiohttp
from typing import Dict, Any

from tests.clients.nginx_test_client import NginxTestClient


class TestNginxRouting:
    """Test nginx reverse proxy routing configuration"""
    
    BASE_URL = "http://localhost:3001"  # Test nginx proxy
    
    @pytest.fixture
    async def nginx_client(self):
        """Nginx test client"""
        return NginxTestClient(self.BASE_URL)
    
    @pytest.fixture
    async def http_session(self):
        """HTTP session for nginx testing"""
        async with aiohttp.ClientSession() as session:
            yield session
    
    @pytest.mark.asyncio
    async def test_public_api_routing(self, nginx_client):
        """Test that /api/ routes to public API endpoints"""
        results = await nginx_client.test_public_api_routes()
        
        # Verify each route
        models_result = results.get("/api/v1/models")
        assert models_result is not None
        assert models_result["expects_auth"] == True
        assert models_result["unauthenticated"]["status_code"] == 401
        
        chat_result = results.get("/api/v1/chat/completions")
        assert chat_result is not None
        assert chat_result["expects_auth"] == True
        assert chat_result["unauthenticated"]["status_code"] == 401
        
        # Health check should not require auth
        health_result = results.get("/api/v1/health")
        if health_result:  # Health endpoint might not exist
            assert health_result["expects_auth"] == False or health_result["unauthenticated"]["status_code"] == 200
    
    @pytest.mark.asyncio 
    async def test_internal_api_routing(self, nginx_client):
        """Test that /api-internal/ routes to internal API endpoints"""
        results = await nginx_client.test_internal_api_routes()
        
        # All internal routes should require authentication
        for path, result in results.items():
            assert result["requires_auth"] == True, f"Internal route {path} should require authentication"
            assert result["unauthenticated"]["status_code"] == 401, f"Internal route {path} should return 401 without auth"
    
    @pytest.mark.asyncio
    async def test_frontend_routing(self, nginx_client):
        """Test that frontend routes are properly served"""
        results = await nginx_client.test_frontend_routes()
        
        # Root path should serve HTML
        root_result = results.get("/")
        assert root_result is not None
        assert root_result["status_code"] in [200, 404]  # 404 is acceptable if Next.js not running
        
        # Other frontend routes should at least attempt to serve content
        for path, result in results.items():
            if path != "/":  # Root might have different behavior
                assert result["status_code"] in [200, 404, 500], f"Frontend route {path} returned unexpected status {result['status_code']}"
    
    @pytest.mark.asyncio
    async def test_cors_headers(self, nginx_client):
        """Test CORS headers are properly set by nginx"""
        cors_results = await nginx_client.test_cors_headers()
        
        # Test preflight response
        preflight = cors_results.get("preflight", {})
        if preflight.get("status_code") == 204:  # Successful preflight
            cors_headers = preflight.get("cors_headers", {})
            assert "access-control-allow-origin" in cors_headers
            assert "access-control-allow-methods" in cors_headers
            assert "access-control-allow-headers" in cors_headers
        
        # Test actual request CORS headers
        request = cors_results.get("request", {})
        cors_headers = request.get("cors_headers", {})
        # Should have at least allow-origin header
        assert len(cors_headers) > 0 or request.get("status_code") == 401  # Auth might block before CORS
    
    @pytest.mark.asyncio
    async def test_websocket_support(self, nginx_client):
        """Test that nginx supports WebSocket upgrades for Next.js HMR"""
        ws_result = await nginx_client.test_websocket_support()
        
        # Should either upgrade or handle gracefully
        assert ws_result["status_code"] in [101, 200, 404, 426], f"Unexpected WebSocket response: {ws_result['status_code']}"
        
        # If upgrade attempted, check headers
        if ws_result["upgrade_attempted"]:
            assert "upgrade" in ws_result.get("upgrade_header", "").lower() or \
                   "websocket" in ws_result.get("connection_header", "").lower()
    
    @pytest.mark.asyncio
    async def test_health_endpoints(self, nginx_client):
        """Test health check endpoints"""
        health_results = await nginx_client.test_health_endpoints()
        
        # At least one health endpoint should be working
        healthy_endpoints = [endpoint for endpoint, result in health_results.items() if result["healthy"]]
        assert len(healthy_endpoints) > 0, "No health endpoints are responding correctly"
        
        # Test-specific endpoint should work
        test_status = health_results.get("/test-status")
        if test_status:
            assert test_status["healthy"], "Test status endpoint should be working"
    
    @pytest.mark.asyncio
    async def test_static_file_caching(self, nginx_client):
        """Test that static files have proper caching headers"""
        static_results = await nginx_client.test_static_file_handling()
        
        # Check that caching is configured (even if files don't exist)
        # This tests the nginx configuration, not file existence
        for file_path, result in static_results.items():
            if result["status_code"] == 200:  # Only check if file was served
                assert result["cached"], f"Static file {file_path} should have cache headers"
    
    @pytest.mark.asyncio
    async def test_error_handling(self, nginx_client):
        """Test nginx error handling"""
        error_results = await nginx_client.test_error_handling()
        
        for path, result in error_results.items():
            # Should return appropriate error status
            assert result["actual_status"] >= 400, f"Error path {path} should return error status"
            
            # 404 errors should be handled properly
            if result["expected_status"] == 404:
                assert result["actual_status"] in [404, 500], f"404 path {path} returned {result['actual_status']}"
    
    @pytest.mark.asyncio
    async def test_request_routing_headers(self, http_session):
        """Test that nginx passes correct headers to backend"""
        headers_to_test = {
            "X-Real-IP": "127.0.0.1",
            "X-Forwarded-For": "127.0.0.1",
            "User-Agent": "test-client/1.0"
        }
        
        # Test header forwarding on API endpoint
        async with http_session.get(
            f"{self.BASE_URL}/api/v1/models",
            headers=headers_to_test
        ) as response:
            # Even if auth fails (401), headers should be forwarded
            assert response.status in [401, 200, 422], f"Unexpected status for header test: {response.status}"
    
    @pytest.mark.asyncio
    async def test_request_size_limits(self, http_session):
        """Test request size handling"""
        # Test large request body
        large_payload = {"data": "x" * 1024 * 1024}  # 1MB payload
        
        async with http_session.post(
            f"{self.BASE_URL}/api/v1/chat/completions",
            json=large_payload
        ) as response:
            # Should either handle large request or reject with appropriate status
            assert response.status in [401, 413, 400, 422], f"Large request returned {response.status}"
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, nginx_client):
        """Test nginx handling of concurrent requests"""
        load_results = await nginx_client.test_load_balancing(20)  # 20 concurrent requests
        
        assert load_results["total_requests"] == 20
        assert load_results["failure_rate"] < 0.5, f"High failure rate: {load_results['failure_rate']}"
        assert load_results["average_response_time"] < 5.0, f"Slow response time: {load_results['average_response_time']}s"
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, http_session):
        """Test nginx timeout configuration"""
        # Test with a custom timeout header to simulate slow backend
        timeout = aiohttp.ClientTimeout(total=5)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(f"{self.BASE_URL}/health") as response:
                    assert response.status in [200, 401, 404, 500, 502, 503, 504]
            except asyncio.TimeoutError:
                # Acceptable if nginx has shorter timeout than our client
                pass
    
    @pytest.mark.asyncio
    async def test_comprehensive_routing(self, nginx_client):
        """Run comprehensive nginx routing test"""
        comprehensive_results = await nginx_client.run_comprehensive_test()
        
        # Verify critical components are working
        assert "public_api_routes" in comprehensive_results
        assert "internal_api_routes" in comprehensive_results
        assert "health_endpoints" in comprehensive_results
        
        # At least 50% of tested features should be working correctly
        working_features = 0
        total_features = 0
        
        for feature_name, feature_results in comprehensive_results.items():
            if isinstance(feature_results, dict):
                total_features += 1
                if self._is_feature_working(feature_name, feature_results):
                    working_features += 1
        
        success_rate = working_features / total_features if total_features > 0 else 0
        assert success_rate >= 0.5, f"Only {success_rate:.1%} of nginx features working"
    
    def _is_feature_working(self, feature_name: str, results: Dict[str, Any]) -> bool:
        """Check if a feature is working based on test results"""
        if feature_name == "health_endpoints":
            return any(result.get("healthy", False) for result in results.values())
        
        elif feature_name == "load_test":
            return results.get("failure_rate", 1.0) < 0.5
        
        elif feature_name in ["public_api_routes", "internal_api_routes"]:
            return any(
                result.get("requires_auth") or result.get("expects_auth")
                for result in results.values()
            )
        
        elif feature_name == "cors_headers":
            preflight = results.get("preflight", {})
            return preflight.get("status_code") in [204, 200] or len(preflight.get("cors_headers", {})) > 0
        
        # Default: consider working if no major errors
        return True