# Brubru Backend Dockerfile
# Production-ready FastAPI application for brubru.beresol.eu

# ============================================
# Stage 1: Base with Python dependencies
# ============================================
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 brubru \
    && useradd --uid 1000 --gid brubru --shell /bin/bash --create-home brubru

WORKDIR /app

# ============================================
# Stage 2: Dependencies installation
# ============================================
FROM base as dependencies

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
# Note: torch and transformers are heavy; consider CPU-only versions for smaller images
RUN pip install --no-cache-dir -r requirements.txt

# ============================================
# Stage 3: Production image
# ============================================
FROM base as production

# Copy installed dependencies from previous stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=brubru:brubru . /app

# Switch to non-root user
USER brubru

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
# Using uvicorn with optimal production settings
CMD ["uvicorn", "main:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "2", \
    "--limit-concurrency", "100", \
    "--limit-max-requests", "10000", \
    "--access-log", \
    "--proxy-headers", \
    "--forwarded-allow-ips", "*"]
