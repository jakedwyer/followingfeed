#!/bin/bash

# Set error handling
set -e

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> /var/log/followfeed.log
}

# Set the working directory
cd /root/followfeed

log "Starting followfeed script"

# Ensure old containers are cleaned up
log "Cleaning up old containers"
docker compose down --remove-orphans || log "Warning: Cleanup of old containers failed"

# Remove old images (optional, uncomment if needed)
# docker image prune -f

# Pull latest images if using a registry (uncomment if needed)
# docker compose pull

# Start the container
log "Starting container"
docker compose up -d

# Wait for the container to finish (timeout after 4 hours)
log "Waiting for container to complete (timeout: 4 hours)"
if timeout 4h docker compose logs -f; then
    log "Container completed successfully"
else
    log "Container timed out after 4 hours"
fi

# Clean up
log "Cleaning up containers"
docker compose down --remove-orphans

log "Script completed"