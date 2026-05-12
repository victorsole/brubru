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

# Install mistralai from a local checkout — the PyPI release was quarantined
# (pypi:project-status="quarantined" on the simple index), and a straight
# git+https install fails because mistralai's pyproject.toml references a
# README-PYPI.md file that's only generated at PyPI publish time and isn't
# in the git tree. Workaround: clone the v1.9.11 tag, touch the missing
# readme stub, install from the local path, then clean up.
RUN git clone --depth 1 --branch v1.9.11 \
        https://github.com/mistralai/client-python.git /tmp/mistralai-src \
    && touch /tmp/mistralai-src/README-PYPI.md \
    && pip install --no-cache-dir /tmp/mistralai-src \
    && rm -rf /tmp/mistralai-src

# Copy and install light requirements (no torch/transformers; mistralai
# is installed above from a local checkout — removed from this file).
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
