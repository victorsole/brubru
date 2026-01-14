# Brubru Backend Dockerfile (Light version for Railway)
# Uses API-based AI instead of local models to reduce image size

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy and install light requirements (no torch/transformers)
COPY requirements-light.txt .
RUN pip install --no-cache-dir -r requirements-light.txt

# Copy application code
COPY . /app

# Create .pth file to add /app to Python path
RUN echo "/app" > /usr/local/lib/python3.11/site-packages/brubru.pth

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "start.py"]
