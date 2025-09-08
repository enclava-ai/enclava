# Backend Dockerfile for Enclava
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
# When building from docker-compose: context is ./backend
# When building from build-images.sh: context is parent dir with enclava/backend path
COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; \
    else pip install --no-cache-dir \
    fastapi \
    uvicorn \
    sqlalchemy \
    psycopg2-binary \
    redis \
    pydantic \
    python-jose \
    python-multipart \
    httpx \
    qdrant-client \
    alembic; fi

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/uploads /plugins

# Create migration script for database migrations
RUN echo '#!/bin/bash\n\
echo "Running database migrations..."\n\
if [ -f /app/alembic.ini ]; then\n\
    alembic upgrade head\n\
else\n\
    echo "No migrations to run"\n\
fi\n\
echo "Migrations complete"' > /usr/local/bin/migrate.sh && \
    chmod +x /usr/local/bin/migrate.sh

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]