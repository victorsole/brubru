# Brubru Backend Dockerfile (Light version for Railway)
# Uses API-based AI instead of local models to reduce image size

FROM python:3.11-slim

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
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy and install light requirements (no torch/transformers)
COPY requirements-light.txt .
RUN pip install --no-cache-dir -r requirements-light.txt

# Copy application code
COPY . /app

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Use entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
