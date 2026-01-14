"""
Public API v1 package - for external clients
"""

from fastapi import APIRouter
from ..v1.auth import router as auth_router
from ..v1.llm import router as llm_router
from ..v1.chatbot import router as chatbot_router
from ..v1.openai_compat import router as openai_router
from ..v1.endpoints.tool_calling import router as tool_calling_router
from ..v1.endpoints.mcp_servers import router as mcp_servers_router
from ..v1.endpoints.responses import router as responses_router
from ..v1.endpoints.conversations import router as conversations_router
from ..v1.endpoints.prompts import router as prompts_router

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

# Include tool-calling API (agent configurations and tool execution)
public_api_router.include_router(
    tool_calling_router, prefix="/tool-calling", tags=["tool-calling"]
)

# Include MCP servers API (MCP server management)
public_api_router.include_router(
    mcp_servers_router, prefix="/mcp-servers", tags=["mcp-servers"]
)

# Include Responses API (OpenAI-compatible agentic responses with tools)
public_api_router.include_router(
    responses_router, tags=["responses"]
)

# Include Conversations API (multi-turn conversation management)
public_api_router.include_router(
    conversations_router, tags=["conversations"]
)

# Include Prompts API (agent config management as prompts)
public_api_router.include_router(
    prompts_router, tags=["prompts"]
)
