FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy only the necessary files
COPY requirements.txt .
COPY api ./api
COPY twitter ./twitter
COPY utils ./utils

# Install Python dependencies using UV
RUN /root/.local/bin/uv pip install --system \
    wheel \
    setuptools \
    && /root/.local/bin/uv pip install --system -r requirements.txt

# Expose the port
EXPOSE 8000

# Run the API server
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"] 