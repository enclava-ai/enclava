"""
API v1 package
"""

from fastapi import APIRouter
from .auth import router as auth_router
from .llm import router as llm_router
from .tee import router as tee_router
from .modules import router as modules_router
from .platform import router as platform_router
from .users import router as users_router
from .api_keys import router as api_keys_router
from .budgets import router as budgets_router
from .audit import router as audit_router
from .settings import router as settings_router
from .analytics import router as analytics_router
from .rag import router as rag_router
from .chatbot import router as chatbot_router
from .prompt_templates import router as prompt_templates_router
from .security import router as security_router
from .plugin_registry import router as plugin_registry_router

# Create main API router
api_router = APIRouter()

# Include authentication routes
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])

# Include LLM proxy routes
api_router.include_router(llm_router, prefix="/llm", tags=["llm"])

# Include TEE routes
api_router.include_router(tee_router, prefix="/tee", tags=["tee"])

# Include modules routes
api_router.include_router(modules_router, prefix="/modules", tags=["modules"])

# Include platform routes
api_router.include_router(platform_router, prefix="/platform", tags=["platform"])

# Include user management routes
api_router.include_router(users_router, prefix="/users", tags=["users"])

# Include API key management routes
api_router.include_router(api_keys_router, prefix="/api-keys", tags=["api-keys"])

# Include budget management routes
api_router.include_router(budgets_router, prefix="/budgets", tags=["budgets"])

# Include audit log routes
api_router.include_router(audit_router, prefix="/audit", tags=["audit"])

# Include settings management routes
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])

# Include analytics routes
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])

# Include RAG routes
api_router.include_router(rag_router, prefix="/rag", tags=["rag"])

# Include chatbot routes
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["chatbot"])

# Include prompt template routes
api_router.include_router(prompt_templates_router, prefix="/prompt-templates", tags=["prompt-templates"])

# Include security routes
api_router.include_router(security_router, prefix="/security", tags=["security"])


# Include plugin registry routes
api_router.include_router(plugin_registry_router, prefix="/plugins", tags=["plugins"])