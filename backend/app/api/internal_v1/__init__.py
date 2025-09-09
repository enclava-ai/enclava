"""
Internal API v1 package - for frontend use only
"""

from fastapi import APIRouter
from ..v1.auth import router as auth_router
from ..v1.modules import router as modules_router
from ..v1.users import router as users_router
from ..v1.api_keys import router as api_keys_router
from ..v1.budgets import router as budgets_router
from ..v1.audit import router as audit_router
from ..v1.settings import router as settings_router
from ..v1.analytics import router as analytics_router
from ..v1.rag import router as rag_router
from ..v1.prompt_templates import router as prompt_templates_router
from ..v1.security import router as security_router
from ..v1.plugin_registry import router as plugin_registry_router
from ..v1.platform import router as platform_router
from ..v1.llm_internal import router as llm_internal_router
from ..v1.chatbot import router as chatbot_router

# Create internal API router
internal_api_router = APIRouter()

# Include authentication routes (frontend only)
internal_api_router.include_router(auth_router, prefix="/auth", tags=["internal-auth"])

# Include modules routes (frontend management)
internal_api_router.include_router(modules_router, prefix="/modules", tags=["internal-modules"])

# Include platform routes (frontend platform management)  
internal_api_router.include_router(platform_router, prefix="/platform", tags=["internal-platform"])

# Include user management routes (frontend user admin)
internal_api_router.include_router(users_router, prefix="/users", tags=["internal-users"])

# Include API key management routes (frontend API key management)
internal_api_router.include_router(api_keys_router, prefix="/api-keys", tags=["internal-api-keys"])

# Include budget management routes (frontend budget management)
internal_api_router.include_router(budgets_router, prefix="/budgets", tags=["internal-budgets"])

# Include audit log routes (frontend audit viewing)
internal_api_router.include_router(audit_router, prefix="/audit", tags=["internal-audit"])

# Include settings management routes (frontend settings)
internal_api_router.include_router(settings_router, prefix="/settings", tags=["internal-settings"])

# Include analytics routes (frontend analytics viewing)
internal_api_router.include_router(analytics_router, prefix="/analytics", tags=["internal-analytics"])

# Include RAG routes (frontend RAG document management)
internal_api_router.include_router(rag_router, prefix="/rag", tags=["internal-rag"])

# Include prompt template routes (frontend prompt template management)
internal_api_router.include_router(prompt_templates_router, prefix="/prompt-templates", tags=["internal-prompt-templates"])

# Include security routes (frontend security settings)
internal_api_router.include_router(security_router, prefix="/security", tags=["internal-security"])

# Include plugin registry routes (frontend plugin management)
internal_api_router.include_router(plugin_registry_router, prefix="/plugins", tags=["internal-plugins"])

# Include internal LLM routes (frontend LLM service access with JWT auth)
internal_api_router.include_router(llm_internal_router, prefix="/llm", tags=["internal-llm"])

# Include chatbot routes (frontend chatbot management)
internal_api_router.include_router(chatbot_router, prefix="/chatbot", tags=["internal-chatbot"])