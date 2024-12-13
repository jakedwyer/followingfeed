#!/bin/bash

# Stop the service
sudo systemctl stop main.service

# Pull latest changes
git pull origin main

# Install or update dependencies
pip install -r requirements.txt

# Restart the service
sudo systemctl start main.service

# Check status
sudo systemctl status main.service

echo "Deployment completed!" 