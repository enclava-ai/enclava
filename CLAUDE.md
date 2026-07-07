This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Enclava is a confidential AI platform providing OpenAI-compatible chatbots and API endpoints with knowledge base access (RAG). It uses privatemode.ai for privacy-protected LLM inference via confidential computing (TEE).

## Warnings and rules
- Do not try to change to timestamps with timezones 
- Use Docker Compose for local containers, not Podman.
- After shipping code that affects the running app, rebuild/recreate containers and smoke-check the public routes before calling the work done.

## Development Commands

### Start Development Environment
```bash
# Start all services (first run will build containers)
sudo docker compose up --build

# Run in background
sudo docker compose up --build -d
```

Application accessible at:
- Main app: http://localhost:1080
- Frontend dev: http://localhost:3002
- Backend API docs: http://localhost:1080/api/v1/docs
- Qdrant dashboard: http://localhost:56333/dashboard

### Container Closeout
```bash
# Always run after completing app changes that should be reflected locally
sudo docker compose up --build -d

# Nginx can keep stale upstream container addresses after backend/frontend recreate
sudo docker compose restart enclava-nginx

# Verify services and public routes
sudo docker compose ps
curl -I --max-time 10 http://localhost:1080/
curl -I --max-time 10 http://localhost:1080/settings/llm
curl -I --max-time 10 http://localhost:1080/api/v1/docs
```

If Docker socket access is configured for the current user, the same commands can be run without `sudo`.

### Backend Testing
```bash
# Run tests with Docker (uses docker-compose.test.yml)
cd backend
sudo docker compose -f ../docker-compose.test.yml run --rm enclava-backend-test pytest

# Run specific test file
sudo docker compose -f ../docker-compose.test.yml run --rm enclava-backend-test pytest tests/test_auth_security.py

# Run single test
sudo docker compose -f ../docker-compose.test.yml run --rm enclava-backend-test pytest tests/test_auth_security.py::test_function_name -v
```

### Backend Linting/Formatting
```bash
cd backend

# Format code
black app/ tests/
isort app/ tests/

# Check linting
flake8 app/ tests/
mypy app/
```

### Frontend Development
```bash
cd frontend
npm run dev      # Development server
npm run build    # Production build
npm run lint     # ESLint
```

### Database Migrations
```bash
# Create new migration (inside backend container)
alembic revision --autogenerate -m "description"

# Apply migrations (runs automatically on container start)
alembic upgrade head
```

## Architecture

### Tech Stack
- **Backend**: FastAPI (Python 3.11), SQLAlchemy async, Pydantic
- **Frontend**: Next.js 16, React 19, TypeScript 6, Tailwind CSS, Radix UI
- **Databases**: PostgreSQL 16, Redis 7, Qdrant (vector DB)
- **LLM Proxy**: privatemode.ai proxy for confidential inference

### Backend Structure (`backend/app/`)
- `api/` - API route handlers
  - `internal_v1/` - Routes for frontend (JWT auth, prefix: `/api-internal/v1`)
  - `public_v1/` - Routes for external clients (API key auth, prefix: `/api/v1`)
  - `v1/` - Shared route implementations
- `services/` - Business logic
  - `llm/` - LLM service with provider abstraction and resilience patterns
  - `rag_service.py` - RAG document processing and retrieval
  - `plugin_*.py` - Plugin system services
  - `mcp_*.py` - MCP (Model Context Protocol) integration
- `models/` - SQLAlchemy ORM models
- `schemas/` - Pydantic request/response schemas
- `core/` - Configuration, security, caching
- `middleware/` - Request middleware (analytics)

### Frontend Structure (`frontend/src/`)
- `app/` - Next.js App Router pages
- `components/` - React components (uses Radix UI primitives in `ui/`)
- `lib/` - Utilities and API client
  - `api-client.ts` - Centralized API client (use instead of raw fetch)
- `contexts/` - React contexts
- `hooks/` - Custom React hooks

### API Design
Two separate API layers with different auth mechanisms:
- **Internal API** (`/api-internal/v1`): JWT auth for frontend, includes management routes (users, settings, analytics)
- **Public API** (`/api/v1`): API key auth for external clients, includes OpenAI-compatible endpoints

OpenAI-compatible endpoints at `/api/v1/chat/completions`, `/api/v1/models`, `/api/v1/embeddings`.

### Key Services
- **LLM Service** (`services/llm/`): Provider abstraction with circuit breaker and retry patterns
- **RAG Service**: Document upload, chunking, embedding, and semantic search via Qdrant
- **Module Manager**: Dynamic module loading and route registration
- **Plugin System**: Auto-discovery and sandboxed execution of plugins
- **Budget Enforcement**: Spend tracking and usage limits per user/API key

## Configuration

Copy `.env.example` to `.env`. Required variables:
- `JWT_SECRET` - JWT signing secret
- `PRIVATEMODE_API_KEY` - API key for privatemode.ai
- `BASE_URL` - Base URL for CORS and frontend URLs

## Code Conventions

### Backend
- Use `black` formatting (88 char line length)
- Use `isort` for import sorting (profile: black)
- Strict mypy typing enabled
- Test markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.db`

### Frontend
- Use `apiClient` from `@/lib/api-client` for API calls (enforced by ESLint)
- Path aliases: `@/` maps to `./src/`
- No `console.log` statements allowed (ESLint error)

### Frontend UX Conventions
- Use semantic design tokens and Tailwind roles (`bg-background`, `text-foreground`, `border-border`, `text-muted-foreground`, status tokens) instead of raw palette utilities or legacy `empire-*`/`enclava-*` classes.
- Use `StatusBadge` for severity/state. Use neutral `Badge` variants for categories, labels, and metadata that are not status.
- Use shared skeleton primitives from `@/components/ui/skeletons` for initial page/list loading. Keep spinners for inline button, upload, refresh, and row-level busy states.
- Use `EmptyState` from `@/components/ui/empty-state` for high-traffic zero states, with value copy and a primary action.
- Use the project `useToast` API from `@/hooks/use-toast` and themed confirmations through `useConfirm`; do not add native `confirm`, `alert`, or `prompt`.
- Run `npm run check:colors` and `npm run check:plumbing` from `frontend/` before shipping frontend UX changes.
