# External Integrations

**Analysis Date:** 2026-07-01

## APIs & External Services

**LLM Providers:**
- PrivateMode.ai proxy - Default confidential LLM provider for chat, embeddings, streaming, and function calling.
  - SDK/Client: custom provider using HTTP clients in `backend/app/services/llm/providers/privatemode.py` through `backend/app/services/llm/service.py`.
  - Auth: `PRIVATEMODE_API_KEY`.
  - Base URL: `PRIVATEMODE_PROXY_URL`, defaulting to `http://privatemode-proxy:8080/v1` in `backend/app/core/config.py`.
  - Runtime service: `privatemode-proxy` image `ghcr.io/edgelesssys/privatemode/privatemode-proxy:latest` in `docker-compose.yml` and `docker-compose.prod.yml`.
- RedPill.ai - Optional confidential LLM provider for chat, embeddings, streaming, function calling, and attestation.
  - SDK/Client: custom provider in `backend/app/services/llm/providers/redpill.py` registered by `backend/app/services/llm/service.py`.
  - Auth: `REDPILL_API_KEY`.
  - Base URL: `REDPILL_BASE_URL`, defaulting to `https://api.redpill.ai/v1` in `backend/app/core/config.py`.
  - Model/test configuration: `REDPILL_TEST_MODEL` and `REDPILL_CONFIDENTIAL_MODEL_PREFIXES` in `backend/app/core/config.py`.

**Attestation Services:**
- NVIDIA NRAS - GPU attestation verification for confidential RedPill models.
  - SDK/Client: HTTP calls from `backend/app/services/llm/attestation/redpill.py`.
  - Auth: not detected in code; endpoint configured by `NVIDIA_NRAS_API_URL`.
- Phala Cloud TDX verifier - TDX attestation verification for confidential RedPill models.
  - SDK/Client: HTTP calls from `backend/app/services/llm/attestation/redpill.py`.
  - Auth: not detected in code; endpoint configured by `PHALA_TDX_VERIFIER_URL`.

**Knowledge Connectors:**
- Notion - Syncs pages and databases into RAG collections.
  - SDK/Client: `notion-client` used by `backend/app/connectors/notion.py`.
  - Auth: connector credentials contain `api_token` or OAuth `access_token`; OAuth app config uses `NOTION_CLIENT_ID` and `NOTION_CLIENT_SECRET` in `backend/app/core/config.py`.
  - OAuth endpoints: `backend/app/api/v1/connectors.py`.
- GitHub - Syncs repositories, issues, pull requests, and README content into RAG collections.
  - SDK/Client: `PyGithub` used by `backend/app/connectors/github.py`.
  - Auth: connector credentials contain `access_token` or `api_token`; OAuth app config uses `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` in `backend/app/core/config.py`.
  - OAuth endpoints: `backend/app/api/v1/connectors.py`.
- Slack - Syncs channel messages and threads into RAG collections.
  - SDK/Client: `slack-sdk` used by `backend/app/connectors/slack.py`.
  - Auth: connector credentials contain `bot_token` or `access_token`; global bot token config is `SLACK_BOT_TOKEN` in `backend/app/core/config.py`.
- Linear - Syncs issues via Linear GraphQL API.
  - SDK/Client: `httpx` and `requests` in `backend/app/connectors/linear.py`.
  - Auth: `LINEAR_API_KEY` for global API key auth or connector-provided API key credentials.
  - Endpoint: `https://api.linear.app/graphql` in `backend/app/connectors/linear.py`.
- Google Drive, Google Docs, Confluence, Jira - Registered connector types without detected implementation files in the scanned source tree.
  - SDK/Client: registry entries in `backend/app/connectors/registry.py`.
  - Auth: not detected.

**Search and Tooling:**
- Brave Search API - Built-in web search tool for current public web information.
  - SDK/Client: `aiohttp` in `backend/app/services/builtin_tools/web_search.py`.
  - Auth: `BRAVE_SEARCH_API_KEY`.
  - Endpoint: `https://api.search.brave.com/res/v1/web/search`.
- External MCP servers - JSON-RPC/SSE tool integrations normalized to OpenAI function calling format.
  - SDK/Client: custom `aiohttp` client in `backend/app/services/mcp_client.py`.
  - Auth: per-server API key and configurable header name stored through `backend/app/services/mcp_server_service.py` and frontend calls in `frontend/src/lib/api-client.ts`.
  - Endpoint: user-configured `server_url`.
- Plugin repository - Remote plugin registry lookup.
  - SDK/Client: `aiohttp` calls in `backend/app/services/plugin_registry.py`.
  - Auth: not detected.
  - Base URL: `PLUGIN_REPOSITORY_URL`, defaulting to `https://plugins.enclava.com` in `backend/app/core/config.py`.

**Notifications and Alerting:**
- SMTP email - Alert notification delivery.
  - SDK/Client: Python standard email/SMTP flow in `backend/app/services/alerts.py`.
  - Auth: `ALERT_SMTP_USERNAME` and `ALERT_SMTP_PASSWORD`.
  - Config: `ALERT_EMAIL_ENABLED`, `ALERT_SMTP_HOST`, `ALERT_SMTP_PORT`, `ALERT_FROM_EMAIL`, `ALERT_TO_EMAILS` in `backend/app/core/config.py`.
- Slack Incoming Webhook - Alert delivery.
  - SDK/Client: `httpx` in `backend/app/services/alerts.py`.
  - Auth: `ALERT_SLACK_WEBHOOK_URL`.
- PagerDuty Events - Critical alert delivery.
  - SDK/Client: `httpx` in `backend/app/services/alerts.py`.
  - Auth: `ALERT_PAGERDUTY_KEY`.

## Data Storage

**Databases:**
- PostgreSQL - Primary relational database for users, auth, modules, RAG metadata, usage, pricing, plugins, notifications, and connector state.
  - Connection: `DATABASE_URL`.
  - Client: SQLAlchemy async engine with `asyncpg` and legacy sync engine with `psycopg2` in `backend/app/db/database.py`.
  - Container: `postgres:16` in `docker-compose.yml`, `postgres:16-alpine` in `docker-compose.prod.yml`, and `postgres:15-alpine` in `docker-compose.test.yml`.
- Qdrant - Vector database for RAG collections and document embeddings.
  - Connection: `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_URL`, and optional `QDRANT_API_KEY`.
  - Client: `qdrant-client` in `backend/app/services/rag_service.py`, `backend/app/modules/rag/main.py`, and `backend/scripts/import_jsonl.py`.
  - Container: `qdrant/qdrant:latest` in `docker-compose.yml`, `docker-compose.prod.yml`, and `docker-compose.test.yml`.
- Redis - Cache, rate-limit support, OAuth state storage, startup dependency, and likely task broker dependency.
  - Connection: `REDIS_URL`.
  - Client: `redis.asyncio` in `backend/app/core/cache.py` and `backend/app/main.py`.
  - Container: `redis:7-alpine` in `docker-compose.yml`, `docker-compose.prod.yml`, and `docker-compose.test.yml`.

**File Storage:**
- Local filesystem only detected.
- Uploaded/document-processing files are handled by backend extract and document modules under `backend/app/modules/extract/`.
- Plugin files and configuration use local paths `PLUGINS_DIR` and `PLUGINS_CONFIG_PATH` from `backend/app/core/config.py`.
- Docker volumes provide persistence for PostgreSQL, Redis, Qdrant, and nginx logs in compose files such as `docker-compose.prod.yml`.

**Caching:**
- Redis cache through `CoreCacheService` in `backend/app/core/cache.py`.
- OAuth state tokens are stored in Redis with `oauth_state:{state}` keys in `backend/app/api/v1/connectors.py`.
- PrivateMode proxy has optional cache settings `PRIVATEMODE_CACHE_MODE` and `PRIVATEMODE_CACHE_SALT` in `docker-compose.yml` and `docker-compose.prod.yml`.

## Authentication & Identity

**Auth Provider:**
- Custom JWT/session authentication.
  - Implementation: JWT settings and validation are configured in `backend/app/core/config.py`; security helpers are in `backend/app/core/security.py`; auth endpoints are in `backend/app/api/v1/auth.py`.
  - Token settings: `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_MINUTES`, and `SESSION_EXPIRE_MINUTES`.
  - Password hashing: `bcrypt` with `BCRYPT_ROUNDS` from `backend/app/core/config.py`.
- API key authentication for programmatic/OpenAI-compatible access.
  - Implementation: `backend/app/services/api_key_auth.py`, `backend/app/models/api_key.py`, and agent/extract routes such as `backend/app/modules/agent/main.py` and `backend/app/api/v1/extract.py`.
  - Prefix: `API_KEY_PREFIX`.
- Connector OAuth for Notion and GitHub only.
  - Implementation: authorization and callback handlers in `backend/app/api/v1/connectors.py`.
  - State storage: Redis via `backend/app/core/cache.py`.
  - Provider credentials: `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`.

## Monitoring & Observability

**Error Tracking:**
- No hosted error tracking provider detected.
- Backend uses structured logging through `backend/app/core/logging.py`.
- Alert delivery for system and budget events is implemented in `backend/app/services/alerts.py`.

**Logs:**
- Backend logging is configured in `backend/app/core/logging.py` and initialized by `backend/app/main.py`.
- Log format and level use `LOG_FORMAT`, `LOG_LEVEL`, and `APP_LOG_LEVEL` in `backend/app/core/config.py`.
- Nginx logs are persisted to Docker volumes in `docker-compose.yml` and `docker-compose.prod.yml`.

**Metrics:**
- Prometheus metrics are enabled through `PROMETHEUS_ENABLED` and `PROMETHEUS_PORT` in `backend/app/core/config.py`.
- Metrics setup is called from `backend/app/main.py` and implemented in `backend/app/services/metrics.py`.
- Internal metrics routes live in `backend/app/api/internal_v1/metrics.py`.
- OpenTelemetry packages are present in `backend/requirements.txt`; collector/exporter configuration was not detected.

## CI/CD & Deployment

**Hosting:**
- Docker Compose deployment is the detected hosting model.
- Development compose file: `docker-compose.yml`.
- Production compose file: `docker-compose.prod.yml`.
- Test compose file: `docker-compose.test.yml`.
- Nginx reverse proxy mounts `nginx/nginx.conf` or `nginx/nginx.test.conf` from compose files.

**CI Pipeline:**
- No `.github/workflows/` files detected in the scanned repo.

## Environment Configuration

**Required env vars:**
- Backend core: `DATABASE_URL`, `JWT_SECRET`, `BASE_URL`.
- Backend service dependencies: `REDIS_URL`, `QDRANT_HOST`, `QDRANT_PORT`, optional `QDRANT_API_KEY`.
- LLM providers: at least one of `PRIVATEMODE_API_KEY` or `REDPILL_API_KEY`; optional `PRIVATEMODE_PROXY_URL`, `REDPILL_BASE_URL`, `REDPILL_TEST_MODEL`, `REDPILL_CONFIDENTIAL_MODEL_PREFIXES`.
- Attestation: `NVIDIA_NRAS_API_URL`, `PHALA_TDX_VERIFIER_URL`.
- Connector OAuth: `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`.
- Connector token defaults: `SLACK_BOT_TOKEN`, `LINEAR_API_KEY`, `CONNECTOR_CREDENTIALS_KEY`.
- Alerts: `ALERT_EMAIL_ENABLED`, `ALERT_SMTP_HOST`, `ALERT_SMTP_PORT`, `ALERT_SMTP_USERNAME`, `ALERT_SMTP_PASSWORD`, `ALERT_FROM_EMAIL`, `ALERT_TO_EMAILS`, `ALERT_SLACK_WEBHOOK_URL`, `ALERT_PAGERDUTY_KEY`.
- Built-in web search: `BRAVE_SEARCH_API_KEY`.
- Frontend public config: `NEXT_PUBLIC_BASE_URL`, `NEXT_PUBLIC_APP_NAME`.

**Secrets location:**
- `.env` file present - contains local environment configuration and was not read.
- `.env.example` file present - example environment configuration exists at repo root.
- Runtime secret names are declared in `backend/app/core/config.py`, `frontend/next.config.js`, `frontend/src/lib/config.ts`, `docker-compose.yml`, and `docker-compose.prod.yml`.
- Connector credentials are encrypted before persistence by code paths in `backend/app/api/v1/connectors.py` and connector sync services.

## Webhooks & Callbacks

**Incoming:**
- Notion OAuth callback: `/api-internal/v1/connectors/oauth/callback`, implemented in `backend/app/api/v1/connectors.py`.
- GitHub OAuth callback: `/api-internal/v1/connectors/oauth/callback`, implemented in `backend/app/api/v1/connectors.py`.
- External MCP server calls are outgoing from Enclava; no incoming MCP webhook endpoint detected.
- No generic external webhook receiver endpoint detected.

**Outgoing:**
- Notion OAuth authorization: `https://api.notion.com/v1/oauth/authorize` from `backend/app/api/v1/connectors.py`.
- Notion OAuth token exchange: `https://api.notion.com/v1/oauth/token` from `backend/app/api/v1/connectors.py`.
- GitHub OAuth authorization: `https://github.com/login/oauth/authorize` from `backend/app/api/v1/connectors.py`.
- GitHub OAuth token exchange: `https://github.com/login/oauth/access_token` from `backend/app/api/v1/connectors.py`.
- Linear GraphQL: `https://api.linear.app/graphql` from `backend/app/connectors/linear.py`.
- Brave Search API: `https://api.search.brave.com/res/v1/web/search` from `backend/app/services/builtin_tools/web_search.py`.
- Slack alert webhooks: `ALERT_SLACK_WEBHOOK_URL` from `backend/app/services/alerts.py`.
- PagerDuty alert events: `ALERT_PAGERDUTY_KEY` from `backend/app/services/alerts.py`.
- User-configured MCP server URLs from `backend/app/services/mcp_client.py`.
- User-configured notification callback URLs are modeled in `backend/app/models/notification.py`.

---

*Integration audit: 2026-07-01*
