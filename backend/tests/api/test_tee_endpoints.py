"""
Test TEE API endpoints.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


class TestTEEEndpoints:
    """Test TEE API endpoints."""

    @pytest.mark.asyncio
    async def test_tee_health_check(self, client: AsyncClient):
        """Test TEE health check endpoint."""
        mock_health = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "version": "1.0.0"
        }
        
        with patch("app.services.tee_service.TEEService.health_check") as mock_check:
            mock_check.return_value = mock_health
            
            response = await client.get(
                "/api/v1/tee/health",
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_tee_capabilities(self, client: AsyncClient):
        """Test TEE capabilities endpoint."""
        mock_capabilities = {
            "hardware_security": True,
            "encryption_at_rest": True,
            "memory_protection": True,
            "supported_models": ["gpt-3.5-turbo", "claude-3-haiku"]
        }
        
        with patch("app.services.tee_service.TEEService.get_tee_capabilities") as mock_caps:
            mock_caps.return_value = mock_capabilities
            
            response = await client.get(
                "/api/v1/tee/capabilities",
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["hardware_security"] is True
        assert "supported_models" in data

    @pytest.mark.asyncio
    async def test_tee_attestation(self, client: AsyncClient):
        """Test TEE attestation endpoint."""
        mock_attestation = {
            "attestation_document": "base64_encoded_document",
            "signature": "signature_data",
            "timestamp": "2024-01-01T00:00:00Z",
            "valid": True
        }
        
        with patch("app.services.tee_service.TEEService.get_attestation") as mock_att:
            mock_att.return_value = mock_attestation
            
            response = await client.get(
                "/api/v1/tee/attestation",
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "attestation_document" in data

    @pytest.mark.asyncio
    async def test_tee_session_creation(self, client: AsyncClient):
        """Test TEE secure session creation."""
        mock_session = {
            "session_id": "secure-session-123",
            "public_key": "public_key_data",
            "expires_at": "2024-01-01T01:00:00Z"
        }
        
        with patch("app.services.tee_service.TEEService.create_secure_session") as mock_session_create:
            mock_session_create.return_value = mock_session
            
            response = await client.post(
                "/api/v1/tee/session",
                json={"model": "gpt-3.5-turbo"},
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "public_key" in data

    @pytest.mark.asyncio
    async def test_tee_metrics(self, client: AsyncClient):
        """Test TEE metrics endpoint."""
        mock_metrics = {
            "total_requests": 1000,
            "successful_requests": 995,
            "failed_requests": 5,
            "avg_response_time": 0.125,
            "privacy_score": 95.8,
            "security_level": "high"
        }
        
        with patch("app.services.tee_service.TEEService.get_privacy_metrics") as mock_metrics_get:
            mock_metrics_get.return_value = mock_metrics
            
            response = await client.get(
                "/api/v1/tee/metrics",
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["privacy_score"] == 95.8
        assert data["security_level"] == "high"

    @pytest.mark.asyncio
    async def test_tee_unauthorized(self, client: AsyncClient):
        """Test TEE endpoints without authentication."""
        response = await client.get("/api/v1/tee/health")
        assert response.status_code == 401
        
        response = await client.get("/api/v1/tee/capabilities")
        assert response.status_code == 401
        
        response = await client.get("/api/v1/tee/attestation")
        assert response.status_code == 401