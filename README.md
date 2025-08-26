# Enclava

**Secure AI Platform with Privacy-First LLM Services**

Enclava is a comprehensive AI platform that provides secure chatbot services, document retrieval (RAG), and LLM integrations with Trusted Execution Environment (TEE) support via privateMode.ai.

## Key Features

- **AI Chatbots** - Customizable chatbots with prompt templates and RAG integration (openai compatible)
- **RAG System** - Document upload, processing, and semantic search with Qdrant
- **TEE Security** - Privacy-protected LLM inference via confidential computing
- **OpenAI Compatible** - Standard API endpoints for seamless integration with existing tools 
- **Budget Management** - Built-in spend tracking and usage limits

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git
- [privatemode.ai](https://privatemode.ai) api key

### 1. Clone Repository

```bash
git clone <repository-url>
cd enclava
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
vim .env
```

**Required Configuration:**
```bash
# Security
JWT_SECRET=your-super-secret-jwt-key-here-change-in-production

# PrivateMode.ai API Key (optional but recommended)
PRIVATEMODE_API_KEY=your-privatemode-api-key

# Base URL for CORS and frontend
BASE_URL=localhost
```

### 3. Deploy with Docker

```bash
# Start all services
docker compose up --build

# Or run in background
docker compose up --build -d
```

### 4. Access Application

- **Main Application**: http://localhost
- **API Documentation**: http://localhost/docs (backend API)
- **Qdrant Dashboard**: http://localhost:56333/dashboard

### 5. Default Login

- **Username**: `admin`
- **Password**: `admin123`

*Change default credentials immediately in production!*

## Documentation

For comprehensive documentation, API references, and advanced configuration:

**[docs.enclava.ai](https://docs.enclava.ai)**

## Architecture

- **Frontend**: Next.js (React/TypeScript) with Tailwind CSS
- **Backend**: FastAPI (Python) with async/await patterns  
- **Database**: PostgreSQL with automatic migrations
- **Vector DB**: Qdrant for document embeddings
- **Cache**: Redis for sessions and performance
- **LLM Service**: Native secure LLM service with TEE support

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Nginx (Main) | 80 | Reverse proxy and main access |
| Backend API | 58000 | FastAPI application (internal) |
| Frontend | 3000 | Next.js application (internal) |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Caching and sessions |
| Qdrant | 56333 | Vector database for RAG |


## Configuration

### Environment Variables

See `.env.example` for all available configuration options.


## Support

- **Documentation**: [docs.enclava.ai](https://docs.enclava.ai)
- **Issues**: Use the GitHub issue tracker
- **Security**: Report security issues privately



---

