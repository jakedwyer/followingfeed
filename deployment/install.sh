#!/bin/bash

# Exit on any error
set -e

echo "Starting Twitter Profile Analyzer installation..."

# Ensure we're in the project root directory
cd "$(dirname "$0")/.."

# Activate existing xfeed virtual environment
echo "Activating xfeed virtual environment..."
source xfeed/bin/activate

# Install any new requirements
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create log directory
echo "Setting up log directory..."
sudo mkdir -p /var/log/twitter-analyzer
sudo chown root:root /var/log/twitter-analyzer

# Install systemd service
echo "Installing systemd service..."
sudo cp deployment/twitter-analyzer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable twitter-analyzer

# Install cron job for monitoring
echo "Setting up monitoring cron job..."
sudo cp deployment/twitter-analyzer-cron /etc/cron.d/twitter-analyzer
sudo chmod 644 /etc/cron.d/twitter-analyzer

# Make monitoring script executable
chmod +x deployment/monitor_service.py

# Start the service
echo "Starting the service..."
sudo systemctl start twitter-analyzer

# Wait a moment for the service to start
sleep 5

# Check service status
echo "Checking service status..."
sudo systemctl status twitter-analyzer

echo "
Installation complete! The Twitter Profile Analyzer API is now running as a service.

You can monitor it using:
- View service logs: journalctl -u twitter-analyzer -f
- View monitoring logs: tail -f /var/log/twitter-analyzer/monitor.log
- Check service status: systemctl status twitter-analyzer
- Restart service: systemctl restart twitter-analyzer

The API is accessible at: http://localhost:8000
Documentation is available at: http://localhost:8000/docs
" 