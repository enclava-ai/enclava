"""
Unit tests for built-in tools (RAG search, web search).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.builtin_tools import (
    BuiltinToolRegistry,
    RAGSearchTool,
    WebSearchTool,
    ToolExecutionContext,
    register_builtin_tools,
)


@pytest.fixture
def execution_context():
    """Create a mock execution context for testing."""
    mock_db = AsyncMock()
    return ToolExecutionContext(
        user_id=1,
        db=mock_db,
        config={}
    )


class TestBuiltinToolRegistry:
    """Test the BuiltinToolRegistry class."""

    def test_registry_register_and_get(self):
        """Test registering and retrieving a tool."""
        BuiltinToolRegistry.clear()

        tool = RAGSearchTool()
        BuiltinToolRegistry.register(tool)

        retrieved = BuiltinToolRegistry.get("rag_search")
        assert retrieved is not None
        assert retrieved.name == "rag_search"

    def test_registry_get_all_returns_tool_objects(self):
        """Test that get_all returns BuiltinTool objects, not OpenAI schemas."""
        BuiltinToolRegistry.clear()
        register_builtin_tools()

        all_tools = BuiltinToolRegistry.get_all()

        assert len(all_tools) == 2
        for tool in all_tools:
            # Should be instances of BuiltinTool subclasses
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'display_name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'parameters_schema')
            # Should NOT be OpenAI format dictionaries
            assert not isinstance(tool, dict)

    def test_builtin_tool_has_display_name(self):
        """Test that all built-in tools have display_name attribute."""
        tools = [RAGSearchTool(), WebSearchTool()]

        for tool in tools:
            assert hasattr(tool, 'display_name')
            assert isinstance(tool.display_name, str)
            assert len(tool.display_name) > 0

    def test_builtin_tool_compatible_with_converter(self):
        """Test that built-in tools have all attributes needed by converter."""
        tools = [RAGSearchTool(), WebSearchTool()]

        for tool in tools:
            # These attributes are accessed by _convert_tools_to_openai_format
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'display_name')
            assert hasattr(tool, 'parameters_schema')

            # Verify types
            assert isinstance(tool.name, str)
            assert isinstance(tool.description, str)
            assert isinstance(tool.display_name, str)
            assert isinstance(tool.parameters_schema, dict)

    def test_registry_is_builtin(self):
        """Test checking if a tool is built-in."""
        BuiltinToolRegistry.clear()
        BuiltinToolRegistry.register(RAGSearchTool())

        assert BuiltinToolRegistry.is_builtin("rag_search")
        assert not BuiltinToolRegistry.is_builtin("nonexistent_tool")

    def test_registry_clear(self):
        """Test clearing the registry."""
        BuiltinToolRegistry.clear()
        BuiltinToolRegistry.register(RAGSearchTool())

        assert len(BuiltinToolRegistry.get_all()) == 1

        BuiltinToolRegistry.clear()
        assert len(BuiltinToolRegistry.get_all()) == 0


class TestRAGSearchTool:
    """Test the RAG Search built-in tool."""

    @pytest.mark.asyncio
    async def test_rag_search_basic(self, execution_context):
        """Test basic RAG search functionality."""
        tool = RAGSearchTool()

        # Mock RAG module
        with patch('app.services.builtin_tools.rag_search.RAGModule') as MockRAG:
            mock_rag = MockRAG.return_value
            mock_rag.enabled = True

            # Mock search results
            mock_document = MagicMock()
            mock_document.content = "This is a test document content"
            mock_document.original_filename = "test.pdf"
            mock_document.file_type = "pdf"
            mock_document.metadata = {"source": "test"}

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.score = 0.95
            mock_result.relevance_score = 0.9

            mock_rag.search_documents = AsyncMock(return_value=[mock_result])

            # Execute search
            result = await tool.execute(
                {"query": "test query", "max_results": 5},
                execution_context
            )

            assert result.success is True
            assert result.error is None
            assert "results" in result.output
            assert len(result.output["results"]) == 1
            assert result.output["results"][0]["filename"] == "test.pdf"

    @pytest.mark.asyncio
    async def test_rag_search_disabled(self, execution_context):
        """Test RAG search when RAG module is disabled."""
        tool = RAGSearchTool()

        with patch('app.services.builtin_tools.rag_search.RAGModule') as MockRAG:
            mock_rag = MockRAG.return_value
            mock_rag.enabled = False

            result = await tool.execute(
                {"query": "test query"},
                execution_context
            )

            assert result.success is False
            assert "not initialized" in result.error.lower()

    @pytest.mark.asyncio
    async def test_rag_search_missing_query(self, execution_context):
        """Test RAG search with missing query parameter."""
        tool = RAGSearchTool()

        result = await tool.execute({}, execution_context)

        assert result.success is False
        assert "required" in result.error.lower()


class TestWebSearchTool:
    """Test the Web Search built-in tool."""

    @pytest.mark.asyncio
    async def test_web_search_basic(self, execution_context):
        """Test basic web search functionality."""
        tool = WebSearchTool()

        with patch.dict('os.environ', {'BRAVE_SEARCH_API_KEY': 'test_key'}):
            with patch('aiohttp.ClientSession') as MockSession:
                # Mock HTTP response
                mock_resp = AsyncMock()
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value={
                    "web": {
                        "results": [
                            {
                                "title": "Test Result",
                                "url": "https://example.com",
                                "description": "Test description",
                                "age": "2024-01-01"
                            }
                        ]
                    }
                })

                mock_session = MockSession.return_value.__aenter__.return_value
                mock_session.get.return_value.__aenter__.return_value = mock_resp

                result = await tool.execute(
                    {"query": "test query", "num_results": 5},
                    execution_context
                )

                assert result.success is True
                assert result.error is None
                assert "results" in result.output
                assert len(result.output["results"]) == 1
                assert result.output["results"][0]["title"] == "Test Result"

    @pytest.mark.asyncio
    async def test_web_search_missing_api_key(self, execution_context):
        """Test web search when API key is not configured."""
        tool = WebSearchTool()

        with patch.dict('os.environ', {}, clear=True):
            result = await tool.execute(
                {"query": "test query"},
                execution_context
            )

            assert result.success is False
            assert "api key not configured" in result.error.lower()

    @pytest.mark.asyncio
    async def test_web_search_api_error(self, execution_context):
        """Test web search when API returns error."""
        tool = WebSearchTool()

        with patch.dict('os.environ', {'BRAVE_SEARCH_API_KEY': 'test_key'}):
            with patch('aiohttp.ClientSession') as MockSession:
                mock_resp = AsyncMock()
                mock_resp.status = 401
                mock_resp.text = AsyncMock(return_value="Invalid API key")

                mock_session = MockSession.return_value.__aenter__.return_value
                mock_session.get.return_value.__aenter__.return_value = mock_resp

                result = await tool.execute(
                    {"query": "test query"},
                    execution_context
                )

                assert result.success is False
                assert "401" in result.error


class TestBuiltinToolsIntegration:
    """Integration tests for built-in tools registration."""

    def test_register_builtin_tools(self):
        """Test that all built-in tools are registered."""
        register_builtin_tools()

        assert BuiltinToolRegistry.is_builtin("rag_search")
        assert BuiltinToolRegistry.is_builtin("web_search")

        all_tools = BuiltinToolRegistry.get_all()
        assert len(all_tools) == 2
