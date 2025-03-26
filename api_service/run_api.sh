#!/bin/bash

# Set error handling
set -e

# Environment setup
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Log function with timestamps
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> /var/log/followfeed_api.log
}

# Error handling function
handle_error() {
    local exit_code=$?
    log "Error occurred in script at line $1, exit code: $exit_code"
    # Ensure cleanup happens even on error
    docker compose down --remove-orphans || true
    exit $exit_code
}

# Set error trap
trap 'handle_error $LINENO' ERR

# Set the working directory
cd /root/followfeed/api_service || {
    log "Failed to change to working directory"
    exit 1
}

# Check if .env file exists in parent directory
if [ ! -f ../.env ]; then
    log "Error: .env file not found in parent directory"
    exit 1
fi

log "Starting followfeed API service"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    log "Error: Docker is not running"
    exit 1
fi

# Ensure old containers are cleaned up
log "Cleaning up old containers"
docker compose down --remove-orphans || log "Warning: Cleanup of old containers failed"

# Start the API container
log "Starting API container"
docker compose up -d followfeed-api

# Monitor the health of the API
log "Monitoring API health"
for i in {1..12}; do
    if curl -s http://localhost:8000/health > /dev/null; then
        log "API is healthy"
        exit 0
    fi
    log "Waiting for API to become healthy... (attempt $i/12)"
    sleep 5
done

log "API failed to become healthy"
docker compose down --remove-orphans
exit 1 