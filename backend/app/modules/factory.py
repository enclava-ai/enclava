"""
Module Factory for Confidential Empire

This factory creates and wires up all modules with their dependencies.
It ensures proper dependency injection while maintaining optimal performance
through direct method calls and minimal indirection.
"""

from typing import Dict, Optional, Any
import logging

# Import all modules
from .rag.main import RAGModule
from .chatbot.main import ChatbotModule, create_module as create_chatbot_module
from .workflow.main import WorkflowModule

# Import services that modules depend on
from app.services.litellm_client import LiteLLMClient

# Import protocols for type safety
from .protocols import (
    RAGServiceProtocol,
    ChatbotServiceProtocol,
    LiteLLMClientProtocol,
    WorkflowServiceProtocol,
    ServiceRegistry,
)

logger = logging.getLogger(__name__)


class ModuleFactory:
    """Factory for creating and wiring module dependencies"""

    def __init__(self):
        self.modules: Dict[str, Any] = {}
        self.initialized = False

    async def create_all_modules(
        self, config: Optional[Dict[str, Any]] = None
    ) -> ServiceRegistry:
        """
        Create all modules with proper dependency injection

        Args:
            config: Optional configuration for modules

        Returns:
            Dictionary of created modules with their dependencies wired
        """
        config = config or {}

        logger.info("Creating modules with dependency injection...")

        # Step 1: Create LiteLLM client (shared dependency)
        litellm_client = LiteLLMClient()

        # Step 2: Create RAG module (no dependencies on other modules)
        rag_module = RAGModule(config=config.get("rag", {}))

        # Step 3: Create chatbot module with RAG dependency
        chatbot_module = create_chatbot_module(
            litellm_client=litellm_client,
            rag_service=rag_module,  # RAG module implements RAGServiceProtocol
        )

        # Step 4: Create workflow module with chatbot dependency
        workflow_module = WorkflowModule(
            chatbot_service=chatbot_module  # Chatbot module implements ChatbotServiceProtocol
        )

        # Store all modules
        modules = {
            "rag": rag_module,
            "chatbot": chatbot_module,
            "workflow": workflow_module,
        }

        logger.info(f"Created {len(modules)} modules with dependencies wired")

        # Initialize all modules
        await self._initialize_modules(modules, config)

        self.modules = modules
        self.initialized = True

        return modules

    async def _initialize_modules(
        self, modules: Dict[str, Any], config: Dict[str, Any]
    ):
        """Initialize all modules in dependency order"""

        # Initialize in dependency order (modules with no deps first)
        initialization_order = [
            ("rag", modules["rag"]),
            ("chatbot", modules["chatbot"]),  # Depends on RAG
            ("workflow", modules["workflow"]),  # Depends on Chatbot
        ]

        for module_name, module in initialization_order:
            try:
                logger.info(f"Initializing {module_name} module...")
                module_config = config.get(module_name, {})

                # Different modules have different initialization patterns
                if hasattr(module, "initialize"):
                    if module_name == "rag":
                        await module.initialize()
                    else:
                        await module.initialize(**module_config)

                logger.info(f"✅ {module_name} module initialized successfully")

            except Exception as e:
                logger.error(f"❌ Failed to initialize {module_name} module: {e}")
                raise RuntimeError(
                    f"Module initialization failed: {module_name}"
                ) from e

    async def cleanup_all_modules(self):
        """Cleanup all modules in reverse dependency order"""
        if not self.initialized:
            return

        # Cleanup in reverse order
        cleanup_order = ["workflow", "chatbot", "rag"]

        for module_name in cleanup_order:
            if module_name in self.modules:
                try:
                    logger.info(f"Cleaning up {module_name} module...")
                    module = self.modules[module_name]
                    if hasattr(module, "cleanup"):
                        await module.cleanup()
                    logger.info(f"✅ {module_name} module cleaned up")
                except Exception as e:
                    logger.error(f"❌ Error cleaning up {module_name}: {e}")

        self.modules.clear()
        self.initialized = False

    def get_module(self, name: str) -> Optional[Any]:
        """Get a module by name"""
        return self.modules.get(name)

    def is_initialized(self) -> bool:
        """Check if factory is initialized"""
        return self.initialized


# Global factory instance
module_factory = ModuleFactory()


# Convenience functions for external use
async def create_modules(config: Optional[Dict[str, Any]] = None) -> ServiceRegistry:
    """Create all modules with dependencies wired"""
    return await module_factory.create_all_modules(config)


async def cleanup_modules():
    """Cleanup all modules"""
    await module_factory.cleanup_all_modules()


def get_module(name: str) -> Optional[Any]:
    """Get a module by name"""
    return module_factory.get_module(name)


def get_all_modules() -> Dict[str, Any]:
    """Get all modules"""
    return module_factory.modules.copy()


# Factory functions for individual modules (for testing/special cases)
def create_rag_module(config: Optional[Dict[str, Any]] = None) -> RAGModule:
    """Create RAG module"""
    return RAGModule(config=config or {})


def create_chatbot_with_rag(
    rag_service: RAGServiceProtocol, litellm_client: LiteLLMClientProtocol
) -> ChatbotModule:
    """Create chatbot module with RAG dependency"""
    return create_chatbot_module(litellm_client=litellm_client, rag_service=rag_service)


def create_workflow_with_chatbot(
    chatbot_service: ChatbotServiceProtocol,
) -> WorkflowModule:
    """Create workflow module with chatbot dependency"""
    return WorkflowModule(chatbot_service=chatbot_service)


# Module registry for backward compatibility
class ModuleRegistry:
    """Registry that provides access to modules (for backward compatibility)"""

    def __init__(self, factory: ModuleFactory):
        self._factory = factory

    @property
    def modules(self) -> Dict[str, Any]:
        """Get all modules (compatible with existing module_manager interface)"""
        return self._factory.modules

    def get(self, name: str) -> Optional[Any]:
        """Get module by name"""
        return self._factory.get_module(name)

    def __getitem__(self, name: str) -> Any:
        """Support dictionary-style access"""
        module = self.get(name)
        if module is None:
            raise KeyError(f"Module '{name}' not found")
        return module

    def keys(self):
        """Get module names"""
        return self._factory.modules.keys()

    def values(self):
        """Get module instances"""
        return self._factory.modules.values()

    def items(self):
        """Get module name-instance pairs"""
        return self._factory.modules.items()


# Create registry instance for backward compatibility
module_registry = ModuleRegistry(module_factory)
