"""
Public API v1 package - for external clients
"""

from fastapi import APIRouter
from ..v1.auth import router as auth_router
from ..v1.llm import router as llm_router
from ..v1.chatbot import router as chatbot_router
from ..v1.openai_compat import router as openai_router

# Create public API router
public_api_router = APIRouter()

# Include authentication routes (needed for login/logout)
public_api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])

# Include OpenAI-compatible routes (chat/completions, models, embeddings)
public_api_router.include_router(openai_router, tags=["openai-compat"])

# Include LLM services (public access for external clients)
public_api_router.include_router(llm_router, prefix="/llm", tags=["public-llm"])

# Include public chatbot API (external chatbot integrations)
public_api_router.include_router(
    chatbot_router, prefix="/chatbot", tags=["public-chatbot"]
)
