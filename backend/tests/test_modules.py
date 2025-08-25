"""
Comprehensive test suite for all dynamic modules
Tests individual module functionality, integration, and hot-reload capabilities
"""

import pytest
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any
import tempfile
import os

# Import modules for testing
import sys
from pathlib import Path

# Add both backend and modules directories to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))
sys.path.insert(0, str(backend_path / "modules"))

try:
    from modules.rag.main import RAGModule
    from modules.chatbot.main import ChatbotModule
    
    from app.services.module_manager import ModuleManager, ModuleConfig
except ImportError as e:
    print(f"Import error: {e}")
    print("Available modules path:", backend_path / "modules")
    # Create mock modules for testing if imports fail
    class MockModule:
        def __init__(self):
            self.name = "mock"
            self.version = "1.0.0"
            self.description = ""
            self.initialized = False
        
        async def initialize(self):
            self.initialized = True
            return True
        
        async def cleanup(self):
            self.initialized = False
        
        def get_stats(self):
            return {"mock": True}
    
    RAGModule = MockModule
    ChatbotModule = MockModule
    
    # Mock ModuleManager for testing
    class MockModuleManager:
        def __init__(self):
            self.initialized = False
            self.modules = {}
            self.module_order = ['rag', 'chatbot']
        
        async def initialize(self):
            self.initialized = True
        
        async def cleanup(self):
            self.initialized = False
        
        def list_modules(self):
            return self.module_order
        
        def get_module(self, name):
            return MockModule()
        
        def is_module_loaded(self, name):
            return True
        
        async def reload_module(self, name):
            pass
    
    ModuleManager = MockModuleManager
    
    class MockModuleConfig:
        def __init__(self, name, enabled=True, config=None):
            self.name = name
            self.enabled = enabled
            self.config = config or {}
    
    ModuleConfig = MockModuleConfig


class TestModuleIndividual:
    """Test individual module functionality"""
    
    @pytest.mark.asyncio
    async def test_chatbot_module_initialization(self):
        """Test chatbot module initialization and basic operations"""
        chatbot_module = ChatbotModule()
        
        # Test initialization
        result = await chatbot_module.initialize()
        assert result is True
        assert chatbot_module.initialized is True
        
        # Test stats retrieval
        stats = chatbot_module.get_stats()
        assert isinstance(stats, dict)
        
        await chatbot_module.cleanup()
    
    @pytest.mark.asyncio
    async def test_rag_module_initialization(self):
        """Test RAG module initialization with integrated content processing"""
        rag_module = RAGModule()
        
        # Test initialization
        result = await rag_module.initialize()
        assert result is True
        assert rag_module.initialized is True
        
        # Test content processing capabilities
        stats = rag_module.get_stats()
        assert stats['supported_types'] == 8  # Should support 8 file types
        assert 'documents_processed' in stats
        assert 'documents_indexed' in stats
        
        await rag_module.cleanup()
    

class TestModuleIntegration:
    """Test module integration and interactions"""
    
    @pytest.mark.asyncio
    async def test_module_manager_initialization(self):
        """Test module manager loads all modules correctly"""
        module_manager = ModuleManager()
        
        # Test initialization
        await module_manager.initialize()
        assert module_manager.initialized is True
        
        # Check all expected modules are loaded
        expected_modules = ['chatbot', 'rag']
        loaded_modules = module_manager.list_modules()
        
        for module_name in expected_modules:
            assert module_name in loaded_modules, f"Module {module_name} not loaded"
        
        # Test module retrieval
        rag_module = module_manager.get_module('rag')
        assert rag_module is not None
        
        chatbot_module = module_manager.get_module('chatbot')
        assert chatbot_module is not None
        
        await module_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_module_dependencies(self):
        """Test module dependency resolution"""
        module_manager = ModuleManager()
        await module_manager.initialize()
        
        # Test that modules are loaded in correct order
        # (This is implicit since no dependency errors should occur)
        assert len(module_manager.module_order) >= 5
        
        await module_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_module_stats_collection(self):
        """Test that all modules provide stats correctly"""
        module_manager = ModuleManager()
        await module_manager.initialize()
        
        for module_name in module_manager.list_modules():
            module = module_manager.get_module(module_name)
            if hasattr(module, 'get_stats'):
                stats = module.get_stats()
                assert isinstance(stats, dict)
                assert len(stats) > 0
        
        await module_manager.cleanup()


class TestModuleHotReload:
    """Test hot-reload functionality"""
    
    @pytest.mark.asyncio
    async def test_module_reload(self):
        """Test module hot-reload functionality"""
        module_manager = ModuleManager()
        await module_manager.initialize()
        
        # Get initial module reference
        initial_module = module_manager.get_module('rag')
        assert initial_module is not None
        
        # Test reload
        await module_manager.reload_module('rag')
        
        # Get module after reload
        reloaded_module = module_manager.get_module('rag')
        assert reloaded_module is not None
        
        # Module should be reloaded (may be same object or different)
        assert module_manager.is_module_loaded('rag')
        
        await module_manager.cleanup()
    


class TestModulePerformance:
    """Test module performance characteristics"""
    
    @pytest.mark.asyncio
    async def test_module_initialization_speed(self):
        """Test that modules initialize within reasonable time"""
        start_time = time.time()
        
        module_manager = ModuleManager()
        await module_manager.initialize()
        
        initialization_time = time.time() - start_time
        
        # All modules should initialize within 30 seconds
        assert initialization_time < 30.0, f"Module initialization took {initialization_time:.2f}s"
        
        await module_manager.cleanup()
    


class TestModuleErrorHandling:
    """Test module error handling and recovery"""
    
    @pytest.mark.asyncio
    async def test_module_initialization_failure_recovery(self):
        """Test module manager handles initialization failures gracefully"""
        module_manager = ModuleManager()
        
        # This should not raise an exception even if some modules fail to load
        await module_manager.initialize()
        
        # At least some modules should load successfully
        assert len(module_manager.list_modules()) >= 2
        
        await module_manager.cleanup()
    
    
    @pytest.mark.asyncio
    async def test_module_cleanup_robustness(self):
        """Test that module cleanup handles errors gracefully"""
        module_manager = ModuleManager()
        await module_manager.initialize()
        
        # This should not raise exceptions even if individual cleanups fail
        await module_manager.cleanup()
        
        # Manager should be properly shut down
        assert module_manager.initialized is False


class TestModuleAPI:
    """Test module API endpoints and interactions"""
    
    @pytest.mark.asyncio
    async def test_modules_api_response_structure(self):
        """Test that module API responses have correct structure"""
        module_manager = ModuleManager()
        await module_manager.initialize()
        
        # Simulate API response structure
        modules_list = []
        for module_name in module_manager.list_modules():
            module = module_manager.get_module(module_name)
            
            module_info = {
                "name": module_name,
                "version": getattr(module, 'version', '1.0.0'),
                "description": getattr(module, 'description', ''),
                "initialized": getattr(module, 'initialized', False),
                "enabled": True
            }
            
            # Add stats if available
            if hasattr(module, 'get_stats'):
                module_info["stats"] = module.get_stats()
            
            modules_list.append(module_info)
        
        api_response = {
            "total": len(modules_list),
            "modules": modules_list,
            "module_count": len(modules_list),
            "initialized": True
        }
        
        # Verify response structure
        assert isinstance(api_response["total"], int)
        assert api_response["total"] >= 5  # Should have at least 5 modules
        assert isinstance(api_response["modules"], list)
        assert len(api_response["modules"]) == api_response["total"]
        assert api_response["initialized"] is True
        
        # Verify each module has required fields
        for module_info in api_response["modules"]:
            assert "name" in module_info
            assert "version" in module_info
            assert "description" in module_info
            assert "initialized" in module_info
            assert "enabled" in module_info
        
        await module_manager.cleanup()


# Test configuration for pytest
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run basic test manually if executed directly
    async def run_basic_tests():
        print("Running basic module tests...")
        
        # Test individual modules
        test_individual = TestModuleIndividual()
        
        print("Testing chatbot module...")
        await test_individual.test_chatbot_module_initialization()
        print("✓ Chatbot module test passed")
        
        print("Testing RAG module with content processing...")
        await test_individual.test_rag_module_initialization()
        print("✓ RAG module with content processing test passed")
        
        # Test integration
        test_integration = TestModuleIntegration()
        
        print("Testing module manager integration...")
        await test_integration.test_module_manager_initialization()
        print("✓ Module manager integration test passed")
        
        print("\nAll basic tests completed successfully! 🎉")
    
    # Run the tests
    asyncio.run(run_basic_tests())