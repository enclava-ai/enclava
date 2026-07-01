FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies
ARG BUILD_DNS_SERVERS="10.0.2.3 10.88.0.1 1.1.1.1 8.8.8.8"
RUN set -eux; \
    # Work around rootless userns + systemd-resolved DNS during image builds
    if ! grep -q "^nameserver" /etc/resolv.conf || grep -q "127.0.0.53" /etc/resolv.conf; then \
        : > /etc/resolv.conf; \
        for ns in $BUILD_DNS_SERVERS; do echo "nameserver $ns" >> /etc/resolv.conf; done; \
        echo "options ndots:0" >> /etc/resolv.conf; \
    fi; \
    echo 'APT::Sandbox::User "root";' > /etc/apt/apt.conf.d/99rootless; \
    apt_lists=/tmp/apt-lists; \
    apt_cache=/tmp/apt-cache; \
    mkdir -p "$apt_lists/partial" "$apt_cache/partial"; \
    DEBIAN_FRONTEND=noninteractive apt-get \
        -o Acquire::ForceIPv4=true \
        -o Dir::State::Lists="$apt_lists" \
        -o Dir::Cache::Archives="$apt_cache" \
        update; \
    DEBIAN_FRONTEND=noninteractive apt-get \
        -o Acquire::ForceIPv4=true \
        -o Dir::State::Lists="$apt_lists" \
        -o Dir::Cache::Archives="$apt_cache" \
        install -y --no-install-recommends \
            build-essential \
            libpq-dev \
            postgresql-client \
            curl \
            ffmpeg \
            poppler-utils \
    ; \
    rm -rf "$apt_lists" "$apt_cache"

# Install CPU-only PyTorch first so sentence-transformers does not pull CUDA wheels.
RUN pip install --no-cache-dir torch==2.12.1+cpu --extra-index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install Python dependencies
COPY requirements.txt .
COPY tests/requirements-test.txt ./tests/
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r tests/requirements-test.txt

# Optional: Download spaCy English model for NLP processing (commented out for faster builds)
# Uncomment if you install requirements-nlp.txt and need entity extraction
# RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Copy and make migration script executable
COPY scripts/migrate.sh /usr/local/bin/migrate.sh
RUN chmod +x /usr/local/bin/migrate.sh

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
