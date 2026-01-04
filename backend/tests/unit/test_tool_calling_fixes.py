"""
Unit tests for tool calling service - validate_tool_availability.

Tests built-in tools, MCP tools, and custom tools validation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.tool_calling_service import ToolCallingService
from app.services.builtin_tools import BuiltinToolRegistry, register_builtin_tools


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_user():
    """Create a mock user."""
    return {"id": 1, "email": "test@example.com"}


class TestValidateToolAvailability:
    """Test validate_tool_availability with built-in and MCP tools."""

    @pytest.mark.asyncio
    async def test_validate_builtin_tools(self, mock_db, mock_user):
        """Test that built-in tools are recognized as available."""
        # Register built-in tools
        BuiltinToolRegistry.clear()
        register_builtin_tools()

        # Create service
        service = ToolCallingService(mock_db)

        # Test validation
        result = await service.validate_tool_availability(
            ["rag_search", "web_search", "code_execution"],
            mock_user
        )

        # All built-in tools should be available
        assert result["rag_search"] is True
        assert result["web_search"] is True
        assert result["code_execution"] is True

    @pytest.mark.asyncio
    async def test_validate_mcp_tools(self, mock_db, mock_user):
        """Test that MCP tools are recognized when server is configured."""
        service = ToolCallingService(mock_db)

        # Mock environment variable for MCP server configuration
        with patch.dict('os.environ', {
            'MCP_ORDER_API_URL': 'http://localhost:3000',
            'MCP_ORDER_API_KEY': 'test-key'
        }):
            # Test validation for MCP tools
            result = await service.validate_tool_availability(
                ["order-api.get_order", "order-api.create_order"],
                mock_user
            )

            # MCP tools should be available when server is configured
            assert result["order-api.get_order"] is True
            assert result["order-api.create_order"] is True

    @pytest.mark.asyncio
    async def test_validate_mcp_tools_not_configured(self, mock_db, mock_user):
        """Test that MCP tools are not available when server is not configured."""
        service = ToolCallingService(mock_db)

        # Ensure no MCP server configuration
        with patch.dict('os.environ', {}, clear=False):
            # Mock database query to return no tools
            mock_tool_mgmt = MagicMock()
            mock_tool_mgmt.get_tool_by_name_and_user = AsyncMock(return_value=None)
            mock_tool_mgmt.get_tools = AsyncMock(return_value=[])
            service.tool_mgmt = mock_tool_mgmt

            # Test validation for MCP tools
            result = await service.validate_tool_availability(
                ["nonexistent-server.tool"],
                mock_user
            )

            # MCP tools should not be available when server is not configured
            assert result["nonexistent-server.tool"] is False

    @pytest.mark.asyncio
    async def test_validate_mixed_tools(self, mock_db, mock_user):
        """Test validation with mix of built-in, MCP, and custom tools."""
        BuiltinToolRegistry.clear()
        register_builtin_tools()

        service = ToolCallingService(mock_db)

        # Mock custom tool in database
        mock_custom_tool = MagicMock()
        mock_custom_tool.can_be_used_by.return_value = True

        mock_tool_mgmt = MagicMock()
        async def mock_get_tool(name, user_id):
            if name == "custom_tool":
                return mock_custom_tool
            return None
        mock_tool_mgmt.get_tool_by_name_and_user = mock_get_tool
        mock_tool_mgmt.get_tools = AsyncMock(return_value=[])
        service.tool_mgmt = mock_tool_mgmt

        # Mock MCP server configuration
        with patch.dict('os.environ', {'MCP_TEST_SERVER_URL': 'http://localhost:3000'}):
            result = await service.validate_tool_availability(
                ["rag_search", "test-server.some_tool", "custom_tool", "nonexistent_tool"],
                mock_user
            )

            # Check results
            assert result["rag_search"] is True  # Built-in
            assert result["test-server.some_tool"] is True  # MCP
            assert result["custom_tool"] is True  # Custom from DB
            assert result["nonexistent_tool"] is False  # Not found

    @pytest.mark.asyncio
    async def test_validate_tool_availability_priority(self, mock_db, mock_user):
        """Test that built-in tools take priority over database tools."""
        BuiltinToolRegistry.clear()
        register_builtin_tools()

        service = ToolCallingService(mock_db)

        # Mock database to have a tool with same name as built-in
        # This should not be called for built-in tools
        mock_tool_mgmt = MagicMock()
        mock_tool_mgmt.get_tool_by_name_and_user = AsyncMock(side_effect=Exception("Should not be called"))
        service.tool_mgmt = mock_tool_mgmt

        # Test validation - should check built-in first and not hit database
        result = await service.validate_tool_availability(
            ["rag_search"],
            mock_user
        )

        # Built-in tool should be found without database query
        assert result["rag_search"] is True
        # Verify database was NOT queried
        mock_tool_mgmt.get_tool_by_name_and_user.assert_not_called()
