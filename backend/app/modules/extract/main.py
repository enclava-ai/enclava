"""Extract main implementation."""

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import log_module_event
from app.db.database import async_session_factory
from app.services.base_module import BaseModule, Permission
from app.services.llm.service import llm_service

from .templates.manager import TemplateManager

logger = logging.getLogger(__name__)


class ExtractModule(BaseModule):
    """
    Extract document processing module for Enclava.

    Provides invoice and receipt data extraction using vision language models.
    Integrates with Enclava's LLM service for unified token tracking.
    """

    version = "1.0.0"
    description = "Invoice and document extraction using vision models"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(module_id="extract", config=config)

    async def initialize(self):
        """
        Initialize Extract on application startup.

        - Initializes LLM service for inference
        - Seeds default templates if not present
        - Validates LLM service has vision-capable models
        """
        log_module_event("extract", "initializing", {"version": self.version})

        if settings.TESTING or settings.LLM_TEST_MODE:
            logger.info("Skipping external LLM provider initialization in test mode")
        else:
            await llm_service.initialize()

        # Seed default templates
        async with async_session_factory() as db:
            await TemplateManager.seed_defaults(db)

        logger.info("Extract initialized")
        logger.info(f"LLM service available: {llm_service._initialized}")
        log_module_event("extract", "initialized", {"success": True})
        self.initialized = True
        return True

    async def cleanup(self):
        """Cleanup module resources on application shutdown."""
        log_module_event("extract", "cleanup", {"success": True})

    def get_required_permissions(self) -> List[Permission]:
        """Return permissions required by Extract."""
        return [
            Permission("extract", "use", "Use Extract"),
        ]

    async def process_request(
        self, request: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a module request.

        Note: Extract uses REST API endpoints rather than this method.
        This is implemented to satisfy the BaseModule abstract method requirement.
        """
        return {
            "error": "Extract uses REST API endpoints. "
            "Use /api/v1/extract/* endpoints instead."
        }


# ModuleManager discovery hook
extract_module = ExtractModule()


# Module factory function for dependency injection
def create_module(config: Optional[Dict[str, Any]] = None) -> ExtractModule:
    """Create Extract instance."""
    return ExtractModule(config=config)
