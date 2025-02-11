#!/bin/bash

# Exit on any error
set -e

echo "Setting up Twitter Profile Analyzer service..."

# Create log directory
sudo mkdir -p /var/log/twitter-analyzer
sudo chown root:root /var/log/twitter-analyzer

# Copy service file to systemd directory
sudo cp deployment/twitter-analyzer.service /etc/systemd/system/

# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable and start the service
sudo systemctl enable twitter-analyzer
sudo systemctl start twitter-analyzer

echo "Service setup complete. Checking status..."
sudo systemctl status twitter-analyzer

echo "
You can monitor the service using:
- View logs: journalctl -u twitter-analyzer -f
- Check status: systemctl status twitter-analyzer
- Restart service: systemctl restart twitter-analyzer
" 