#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created virtual environment"
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create development environment file if it doesn't exist
if [ ! -f ".env.development" ]; then
    cp .env .env.development
    echo "Created .env.development - Please update it with your development credentials"
fi

# Create necessary directories
mkdir -p logs
mkdir -p output

echo "Development environment setup complete!"
echo "Next steps:"
echo "1. Update .env.development with your development credentials"
echo "2. Run your application using: python main.py" 