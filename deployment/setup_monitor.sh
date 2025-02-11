#!/bin/bash

# Make monitor script executable
chmod +x deployment/monitor_service.py

# Create log directory if it doesn't exist
mkdir -p /var/log/twitter-analyzer

# Create log files if they don't exist
touch /var/log/twitter-analyzer/monitor.log
touch /var/log/twitter-analyzer/monitor-error.log

# Set proper permissions
chown -R root:root /var/log/twitter-analyzer
chmod 644 /var/log/twitter-analyzer/*.log

# Install systemd service
cp deployment/twitter-analyzer-monitor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable twitter-analyzer-monitor
systemctl start twitter-analyzer-monitor

echo "Monitor service installed and started. Check status with: systemctl status twitter-analyzer-monitor" 