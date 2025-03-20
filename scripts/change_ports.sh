#!/bin/bash

# Script to change ports for FollowFeed and Nitter applications
# Usage: ./change_ports.sh [api_port] [nitter_port]

# Default values
DEFAULT_API_PORT=8000
DEFAULT_NITTER_PORT=8081

# Get command line arguments or use defaults
API_PORT=${1:-$DEFAULT_API_PORT}
NITTER_PORT=${2:-$DEFAULT_NITTER_PORT}

# Check if ports are valid numbers
if ! [[ "$API_PORT" =~ ^[0-9]+$ ]] || ! [[ "$NITTER_PORT" =~ ^[0-9]+$ ]]; then
    echo "Error: Ports must be valid numbers"
    echo "Usage: ./change_ports.sh [api_port] [nitter_port]"
    exit 1
fi

# Check if ports are in valid range
if [ "$API_PORT" -lt 1024 ] || [ "$API_PORT" -gt 65535 ] || [ "$NITTER_PORT" -lt 1024 ] || [ "$NITTER_PORT" -gt 65535 ]; then
    echo "Error: Ports must be between 1024 and 65535"
    exit 1
fi

# Check if ports are the same
if [ "$API_PORT" -eq "$NITTER_PORT" ]; then
    echo "Error: API_PORT and NITTER_PORT cannot be the same"
    exit 1
fi

# Update .env file
echo "Updating port configuration in .env file..."
# Check if API_PORT already exists in .env
if grep -q "^API_PORT=" "../.env"; then
    # Replace existing API_PORT
    sed -i "s/^API_PORT=.*/API_PORT=$API_PORT/" "../.env"
else
    # Add API_PORT if it doesn't exist
    echo "API_PORT=$API_PORT" >> "../.env"
fi

# Check if NITTER_PORT already exists in .env
if grep -q "^NITTER_PORT=" "../.env"; then
    # Replace existing NITTER_PORT
    sed -i "s/^NITTER_PORT=.*/NITTER_PORT=$NITTER_PORT/" "../.env"
else
    # Add NITTER_PORT if it doesn't exist
    echo "NITTER_PORT=$NITTER_PORT" >> "../.env"
fi

echo "Port configuration updated:"
echo "API_PORT=$API_PORT"
echo "NITTER_PORT=$NITTER_PORT"

# Check if Docker is running
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo "Docker is running. Do you want to restart the containers? (y/n)"
    read -r restart_docker
    if [[ "$restart_docker" =~ ^[Yy]$ ]]; then
        echo "Restarting Docker containers..."
        cd .. && docker-compose down && docker-compose up -d
    fi
fi

# Check if systemd services are installed
if [ -f "/etc/systemd/system/twitter-analyzer.service" ]; then
    echo "SystemD service found. Do you want to restart the service? (y/n)"
    read -r restart_service
    if [[ "$restart_service" =~ ^[Yy]$ ]]; then
        echo "Restarting twitter-analyzer service..."
        sudo systemctl daemon-reload
        sudo systemctl restart twitter-analyzer.service
    fi
fi

echo "Port configuration complete!" 