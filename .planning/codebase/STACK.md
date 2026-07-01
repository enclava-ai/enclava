# Technology Stack

**Analysis Date:** 2026-07-01

## Languages

**Primary:**
- Python 3.11 - Backend API, services, modules, migrations, and tests in `backend/app/`, `backend/alembic/`, and `backend/tests/`; runtime image is `python:3.11-slim` in `backend/Dockerfile`.
- TypeScript 6.0.3 - Frontend application source in `frontend/src/`; compiler config is `frontend/tsconfig.json`.

**Secondary:**
- JavaScript - Next.js, Tailwind, PostCSS, and ESLint configuration in `frontend/next.config.js`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`, and `frontend/eslint.config.mjs`.
- SQL/Alembic Python migrations - Database schema migrations in `backend/alembic/`.
- Shell - Operational scripts such as `backend/scripts/migrate.sh`.
- YAML - Docker Compose and module/plugin metadata in `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.test.yml`, and `backend/app/modules/*/module.yaml`.

## Runtime

**Environment:**
- Backend: CPython 3.11 with Uvicorn serving FastAPI from `backend/app/main.py`.
- Frontend: Node.js 26 on Alpine Linux, using Next.js standalone output from `frontend/Dockerfile`.
- Container orchestration: Docker Compose defines nginx, backend, frontend, PostgreSQL, Redis, Qdrant, and PrivateMode proxy services in `docker-compose.yml` and `docker-compose.prod.yml`.

**Package Manager:**
- Frontend: npm, driven by `frontend/package.json`.
- Frontend lockfile: present at `frontend/package-lock.json`.
- Backend: pip requirements, driven by `backend/requirements.txt`.
- Backend lockfile: no generated pip lockfile detected.

## Frameworks

**Core:**
- FastAPI 0.138.2 - Backend HTTP API, middleware, router registration, and lifecycle in `backend/app/main.py`.
- SQLAlchemy 2.0.51 - ORM and async/sync database engines in `backend/app/db/database.py` and models under `backend/app/models/`.
- Alembic 1.18.5 - Database migrations in `backend/alembic/`.
- Pydantic 2.13.4 and pydantic-settings 2.14.2 - Settings and request/response validation in `backend/app/core/config.py` and schemas under `backend/app/schemas/`.
- Next.js 16.2.9 - Frontend app router and server/API route surface under `frontend/src/app/`.
- React 19.2.7 and React DOM 19.2.7 - Frontend UI components under `frontend/src/components/`.
- Tailwind CSS 4.3.2 - Frontend styling configured by `frontend/tailwind.config.js` and `frontend/postcss.config.js`.
- Radix UI - Primitive UI components listed in `frontend/package.json`.

**Testing:**
- pytest 9.1.1 - Backend tests under `backend/tests/`, configured in `backend/pyproject.toml`.
- pytest-asyncio 1.4.0 - Async backend tests configured with `asyncio_mode = "auto"` in `backend/pyproject.toml`.
- pytest-cov 7.1.0 - Coverage for `app` with 80% minimum in `backend/pyproject.toml`.
- No frontend test runner detected in `frontend/package.json`.

**Build/Dev:**
- Uvicorn 0.49.0 - ASGI server command in `backend/Dockerfile`.
- Docker and Docker Compose - Runtime topology in `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `docker-compose.prod.yml`, and `docker-compose.test.yml`.
- ESLint 10.6.0 with `@next/eslint-plugin-next`, `typescript-eslint`, and React Hooks plugin - Frontend linting configured in `frontend/eslint.config.mjs`.
- Black 26.5.1, isort 8.0.1, flake8 7.3.0, mypy 2.1.0 - Backend formatting, import sorting, linting, and type checking configured in `backend/pyproject.toml` and `backend/requirements.txt`.

## Key Dependencies

**Critical:**
- `fastapi==0.138.2` - Main backend API framework in `backend/app/main.py`.
- `uvicorn[standard]==0.49.0` - Backend ASGI runtime in `backend/Dockerfile`.
- `sqlalchemy==2.0.51`, `asyncpg==0.31.0`, `psycopg2-binary==2.9.12` - PostgreSQL access through async and sync engines in `backend/app/db/database.py`.
- `redis==8.0.1` - Redis cache and OAuth state storage in `backend/app/core/cache.py` and startup checks in `backend/app/main.py`.
- `qdrant-client==1.18.0` - Vector storage for RAG in `backend/app/services/rag_service.py` and `backend/app/modules/rag/main.py`.
- `python-jose[cryptography]==3.5.0`, `bcrypt==5.0.0`, `cryptography==49.0.0`, `itsdangerous==2.2.0` - JWT, password hashing, credential encryption, and session/security flows in `backend/app/core/security.py`, `backend/app/core/config.py`, and connector credential handling in `backend/app/api/v1/connectors.py`.
- `httpx==0.28.1` and `aiohttp==3.14.1` - Outbound HTTP clients for OAuth, providers, Linear, MCP, plugin registry, and built-in web search in `backend/app/api/v1/connectors.py`, `backend/app/connectors/linear.py`, `backend/app/services/mcp_client.py`, and `backend/app/services/builtin_tools/web_search.py`.
- `next==16.2.9`, `react==19.2.7`, `react-dom==19.2.7` - Frontend framework stack in `frontend/package.json`.

**Infrastructure:**
- `docker==7.1.0` - Tool execution and Docker sandbox integration referenced by `backend/app/services/builtin_tools/code_execution.py` and tool execution services.
- `celery==5.6.3`, `flower==2.0.1` - Background task dependencies listed in `backend/requirements.txt`; task modules live under `backend/app/tasks/`.
- `prometheus-client==0.25.0`, `opentelemetry-api==1.43.0`, `opentelemetry-sdk==1.43.0`, `psutil==7.2.2`, `structlog==26.1.0` - Metrics, observability, and logging in `backend/app/services/metrics.py`, `backend/app/api/internal_v1/metrics.py`, and `backend/app/core/logging.py`.
- `sentence-transformers==5.6.0`, `tiktoken==0.13.0`, `numpy>=1.26.0` - Embedding and token-related RAG/LLM processing in `backend/app/services/rag_service.py` and `backend/app/services/llm/`.
- `markitdown==0.1.6`, `python-docx==1.2.0`, `Pillow==12.2.0`, `pdf2image==1.17.0` - Document extraction and image/PDF processing in `backend/app/modules/extract/`.
- `notion-client==3.1.0`, `PyGithub==2.9.1`, `slack-sdk==3.43.0` - Connector SDKs in `backend/app/connectors/notion.py`, `backend/app/connectors/github.py`, and `backend/app/connectors/slack.py`.
- `lucide-react==1.22.0`, `sonner==2.0.7`, `react-hot-toast==2.6.0`, `react-markdown==10.1.0`, `remark-gfm==4.0.1`, `rehype-highlight==7.0.2` - Frontend icons, notifications, and markdown rendering in `frontend/package.json`.

## Configuration

**Environment:**
- Backend settings are centralized in `backend/app/core/config.py` using `pydantic_settings.BaseSettings` with `model_config.env_file = ".env"`.
- `.env` file present - contains local environment configuration and was not read.
- `.env.example` file present - example environment configuration exists at repo root.
- Critical backend environment variables include `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `BASE_URL`, `PRIVATEMODE_API_KEY`, `REDPILL_API_KEY`, `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY`, connector OAuth credentials, alert settings, and rate-limit settings from `backend/app/core/config.py`.
- Frontend public configuration uses `NEXT_PUBLIC_BASE_URL` and `NEXT_PUBLIC_APP_NAME` in `frontend/src/lib/config.ts`, `frontend/src/lib/url-utils.ts`, and `frontend/next.config.js`.

**Build:**
- Backend container build: `backend/Dockerfile`.
- Backend production/migration container builds: `backend/Dockerfile.prod` and `backend/Dockerfile.migrate`.
- Frontend container build: `frontend/Dockerfile`.
- Docker Compose runtime: `docker-compose.yml`, `docker-compose.prod.yml`, and `docker-compose.test.yml`.
- Next.js config: `frontend/next.config.js`.
- TypeScript config: `frontend/tsconfig.json`.
- ESLint config: `frontend/eslint.config.mjs`.
- Tailwind/PostCSS config: `frontend/tailwind.config.js` and `frontend/postcss.config.js`.
- Python tool config: `backend/pyproject.toml`.
- Python dependency manifest: `backend/requirements.txt`.

## Platform Requirements

**Development:**
- Docker and Docker Compose are the primary full-stack runtime because `docker-compose.yml` provisions nginx, backend, frontend, PostgreSQL, Redis, Qdrant, and PrivateMode proxy.
- Backend local runtime requires Python 3.11, system packages used by `backend/Dockerfile` such as PostgreSQL client libraries, ffmpeg, and poppler-utils, plus a configured `DATABASE_URL`.
- Frontend local runtime requires Node.js 26-compatible npm environment and `frontend/package-lock.json`.
- PostgreSQL, Redis, and Qdrant must be reachable for normal backend startup; checks run in `backend/app/main.py`.

**Production:**
- Production deployment is containerized through `docker-compose.prod.yml`.
- Nginx reverse proxy fronts application traffic using `nginx/nginx.conf` mounted by `docker-compose.prod.yml`.
- Backend runs FastAPI/Uvicorn from `backend/app/main.py`.
- Frontend runs Next.js standalone server generated by `frontend/Dockerfile`.
- Persistent services include PostgreSQL, Redis, Qdrant, and nginx logs via Docker volumes in `docker-compose.prod.yml`.

---

*Stack analysis: 2026-07-01*
