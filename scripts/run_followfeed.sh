#!/bin/bash

# Set error handling
set -e

# Environment setup
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Log function with timestamps
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> /var/log/followfeed.log
}

# Error handling function
handle_error() {
    local exit_code=$?
    log "Error occurred in script at line $1, exit code: $exit_code"
    # Ensure cleanup happens even on error
    cd /root/followfeed/docker && docker compose down --remove-orphans || true
    exit $exit_code
}

# Set error trap
trap 'handle_error $LINENO' ERR

# Set the working directory
cd /root/followfeed || {
    log "Failed to change to working directory"
    exit 1
}

# Check if .env file exists
if [ ! -f .env ]; then
    log "Error: .env file not found"
    exit 1
fi

log "Starting followfeed script"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    log "Error: Docker is not running"
    exit 1
fi

# Ensure old containers are cleaned up
log "Cleaning up old containers"
cd docker && docker compose down --remove-orphans || log "Warning: Cleanup of old containers failed"

# Clean up old logs if they're too large (keep last 100MB)
if [ -f /var/log/followfeed.log ] && [ $(wc -c < /var/log/followfeed.log) -gt 104857600 ]; then
    tail -c 104857600 /var/log/followfeed.log > /var/log/followfeed.log.tmp
    mv /var/log/followfeed.log.tmp /var/log/followfeed.log
    log "Log file rotated"
fi

# Start the container
log "Starting followfeed container"
docker compose up -d followfeed

# Wait for the container to finish (timeout after 4 hours)
log "Waiting for container to complete (timeout: 4 hours)"
if timeout 4h docker compose logs -f followfeed; then
    log "Container completed successfully"
else
    log "Container timed out after 4 hours"
    docker compose down --remove-orphans
    exit 1
fi

# Check container exit code
if [ "$(docker compose ps -a --format '{{.ExitCode}}' followfeed | head -1)" != "0" ]; then
    log "Container exited with non-zero status"
    docker compose down --remove-orphans
    exit 1
fi

# Clean up
log "Cleaning up containers"
docker compose down --remove-orphans

log "Script completed successfully"