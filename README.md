# Enclava

**Confidential AI Platform for Businesses**

Enclava is a comprehensive AI platform that makes privacy practical. It provides easy-to-create OpenAI-compatible chatbots and API endpoints with knowledge base access (RAG), all powered by confidential computing through [privatemode.ai](https://privatemode.ai).

## Key Features

- **AI Chatbots** - Customizable chatbots with prompt templates and RAG integration (OpenAI compatible)
- **RAG System** - Document upload, processing, and semantic search with Qdrant vector database
- **TEE Security** - Privacy-protected LLM inference via PrivateMode.ai confidential computing
- **OpenAI-Compatible API** - Standard API endpoints for seamless integration with existing tools
- **Budget Management** - Built-in spend tracking and usage limits
- **Confidential Processing** - All AI inference runs through PrivateMode.ai secure infrastructure
- **Team Collaboration** - Multi-user support with role-based access control
- **Document Processing** - Support for PDF, TXT, DOCX, and more file formats

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Features](#features)
- [API Documentation](#api-documentation)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git
- 4GB+ RAM
- [privatemode.ai](https://privatemode.ai) API key (required)

### Installation

```bash
# Clone the repository
git clone https://github.com/enclava-ai/enclava.git
cd enclava-kubernetes

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start the platform
docker compose up -d

# Access the application
open http://localhost
```

**Default Credentials:**
- Username: `admin`
- Password: `admin123`

**Important**: Change default credentials immediately in production!

## Architecture

Enclava uses a microservices architecture with the following components:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│    Nginx    │────▶│   Backend   │
│  (Next.js)  │     │   (Proxy)   │     │  (FastAPI)  │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────┐
                    │                          │                      │
              ┌─────▼─────┐          ┌────────▼────────┐     ┌───────▼───────┐
              │ PostgreSQL │          │     Redis       │     │    Qdrant     │
              │    (DB)    │          │   (Cache)       │     │ (Vector DB)   │
              └───────────┘          └─────────────────┘     └───────────────┘
```

### Components

- **Frontend**: Next.js application with React and TypeScript
- **Backend**: FastAPI application with Python for API services
- **PostgreSQL**: Primary database for user data and configurations
- **Redis**: Caching and session management
- **Qdrant**: Vector database for semantic search and RAG
- **Nginx**: Reverse proxy and load balancer

## Features

### AI Capabilities

- **Custom Chatbots**: Create domain-specific AI assistants
- **Prompt Templates**: Reusable prompt configurations
- **Context Management**: Intelligent conversation history handling
- **Model Switching**: Seamlessly switch between AI providers

### Knowledge Management

- **Document Upload**: Support for multiple file formats
- **Semantic Search**: Vector-based similarity search
- **Knowledge Bases**: Organize documents into collections
- **Auto-indexing**: Automatic document processing and embedding

### Security & Privacy

- **Confidential Computing**: TEE-based secure inference
- **Data Encryption**: End-to-end encryption for sensitive data
- **Access Control**: Role-based permissions
- **Audit Logging**: Comprehensive activity tracking

### Integration

- **OpenAI-Compatible API**: Drop-in replacement for OpenAI API format (powered by PrivateMode.ai)
- **REST API**: Full-featured RESTful API
- **Webhooks**: Event-driven integrations
- **SDK Support**: Python and JavaScript SDKs (coming soon)

## API Documentation

Enclava provides OpenAI-compatible API endpoints powered by PrivateMode.ai:

### Chat Completions
```bash
curl -X POST http://localhost/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
# Processed securely through PrivateMode.ai infrastructure
```

### Embeddings
```bash
curl -X POST http://localhost/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "text-embedding-ada-002",
    "input": "Your text here"
  }'
```

Full API documentation available at http://localhost/docs after deployment.

## Deployment

Enclava supports multiple deployment options:

### Docker Compose (Recommended for getting started)
```bash
docker compose up -d
```

### Kubernetes
```bash
kubectl apply -k deploy/k8s/base/
```

### Production Deployment
For production deployments with SSL, monitoring, and scaling, see the [Deployment Guide](deploy/README.md).

## Configuration

Key configuration options in `.env`:

```env
# Required
PRIVATEMODE_API_KEY=your-privatemode-api-key
JWT_SECRET=your-secure-secret-key
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=secure-password
POSTGRES_PASSWORD=secure-db-password
```

See [.env.example](.env.example) for all configuration options.

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone repo
git clone https://github.com/enclava-ai/enclava.git
cd enclava-kubernetes

# Install dependencies
cd backend && pip install -r requirements-dev.txt
cd ../frontend && npm install

# Run tests
cd backend && pytest
cd ../frontend && npm test
```

## Support

- **Documentation**: [docs.enclava.ai](https://docs.enclava.ai)
- **GitHub Issues**: [github.com/enclava-ai/enclava/issues](https://github.com/enclava-ai/enclava/issues)
- **Discord Community**: [discord.gg/enclava](https://discord.gg/enclava)
- **Security Issues**: security@enclava.ai

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [PrivateMode.ai](https://privatemode.ai) for confidential computing infrastructure
- [Qdrant](https://qdrant.tech) for vector database
- The open-source community for amazing tools and libraries

---

**Built by the Enclava Team**

