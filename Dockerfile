# Use Python 3.12 slim as base image
FROM python:3.12-slim

# Install system dependencies including Chromium and required libraries
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    default-jdk \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    xdg-utils \
    chromium \
    chromium-driver \
    build-essential \
    python3-dev \
    gcc \
    g++ \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and setup directories
RUN useradd -m appuser && \
    mkdir -p /app/logs /app/data /tmp/chrome-data /app/screenshots /app/output && \
    # Create Xvfb directories with correct permissions
    mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix && \
    # Set up Chrome directories and permissions
    mkdir -p /home/appuser/.config/chromium && \
    # Set correct permissions for app directories
    chown -R appuser:appuser /home/appuser && \
    chmod -R 755 /app && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY --chown=appuser:appuser requirements.txt .

# Install Python dependencies with build tools
RUN pip install --no-cache-dir wheel setuptools && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
    uvloop \
    aiodns \
    brotlipy

# Copy the rest of the application
COPY --chown=appuser:appuser . .

# Ensure all application files have correct permissions
RUN chmod -R 755 /app/screenshots /app/output /app/logs && \
    chown -R appuser:appuser /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DISPLAY=:99
ENV DBUS_SESSION_BUS_ADDRESS=/dev/null
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV PYTHONIOENCODING=utf-8
ENV PYTHONASYNCIO_DEBUG=1
ENV AIOHTTP_NO_EXTENSIONS=1
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "python.*main\.py" || exit 1

# Start Xvfb and the application
CMD mkdir -p /app/screenshots /app/output && \
    Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset & \
    sleep 2 && \
    python -X dev main.py