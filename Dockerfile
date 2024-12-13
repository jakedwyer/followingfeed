# Use Python 3.12 slim as base image
FROM python:3.12-slim

# Install system dependencies including Chrome and required libraries
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
    && rm -rf /var/lib/apt/lists/*

# Install Chrome/Chromium based on architecture
RUN if [ "$(uname -m)" = "aarch64" ]; then \
        # ARM64 - Install Chromium
        apt-get update && apt-get install -y \
        chromium \
        chromium-driver \
        && apt-get clean; \
    else \
        # x86_64 - Install Chrome
        wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
        && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
        && apt-get update \
        && apt-get install -y google-chrome-stable \
        && CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d'.' -f1-3) \
        && CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}") \
        && wget -q -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip \
        && unzip /tmp/chromedriver.zip -d /usr/local/bin \
        && rm /tmp/chromedriver.zip \
        && chmod +x /usr/local/bin/chromedriver \
        && apt-get clean; \
    fi

# Set working directory
WORKDIR /app

# Create non-root user and setup directories
RUN useradd -m appuser && \
    mkdir -p /app/logs /app/data /tmp/chrome-data && \
    chown -R appuser:appuser /app /tmp/chrome-data && \
    # Create Xvfb directories with correct permissions
    mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix && \
    # Set up Chrome directories and permissions
    mkdir -p /home/appuser/.config/chromium && \
    chown -R appuser:appuser /home/appuser/.config

# Copy requirements first to leverage Docker cache
COPY --chown=appuser:appuser requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY --chown=appuser:appuser . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DISPLAY=:99
ENV DBUS_SESSION_BUS_ADDRESS=/dev/null

# Set Chrome/Chromium paths based on architecture
RUN if [ "$(uname -m)" = "aarch64" ]; then \
        echo "export CHROME_BIN=/usr/bin/chromium" >> /home/appuser/.bashrc && \
        echo "export CHROMEDRIVER_PATH=/usr/bin/chromedriver" >> /home/appuser/.bashrc; \
    else \
        echo "export CHROME_BIN=/usr/bin/google-chrome" >> /home/appuser/.bashrc && \
        echo "export CHROMEDRIVER_PATH=/usr/local/bin/chromedriver" >> /home/appuser/.bashrc; \
    fi

USER appuser

# Start Xvfb and the application
CMD Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset & \
    sleep 2 && \
    python main.py