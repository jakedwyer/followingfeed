#!/bin/bash

# Set the working directory
cd /root/followfeed

# Stop any existing container
docker compose down

# Start the container
docker compose up -d

# Wait for the container to finish (optional - adjust timeout as needed)
timeout 2h docker compose logs -f

# Clean up
docker compose down