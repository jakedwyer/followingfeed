# NOTE: This is an alternative API Dockerfile template that's not currently in use.
# The active API Dockerfile is located at /root/followfeed/api_service/Dockerfile.
# This file is kept for reference purposes only.

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    python3-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and setup directories
RUN useradd -m appuser && \
    mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy requirements first to leverage Docker cache
COPY --chown=appuser:appuser requirements.txt .

# Install Python dependencies using UV
RUN /root/.local/bin/uv pip install --system \
    wheel \
    setuptools \
    && /root/.local/bin/uv pip install --system -r requirements.txt \
    && /root/.local/bin/uv pip install --system \
    uvicorn[standard] \
    gunicorn \
    uvloop \
    httptools

# Copy the rest of the application
COPY --chown=appuser:appuser . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the API server
CMD ["gunicorn", "api.app:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"] 