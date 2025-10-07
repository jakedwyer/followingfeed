#!/bin/bash

# FollowFeed Execution Script
# This script runs the main.py script with proper error handling and logging

# Set error handling
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create logs directory if it doesn't exist
mkdir -p logs

# Log file location
LOG_FILE="logs/followfeed.log"

# Log function with timestamps
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling function
handle_error() {
    local exit_code=$?
    log "Error occurred in script at line $1, exit code: $exit_code"
    exit $exit_code
}

# Set error trap
trap 'handle_error $LINENO' ERR

log "========================================="
log "Starting FollowFeed"
log "========================================="

# Check if .env file exists
if [ ! -f .env ]; then
    log "Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    log "Error: python3 is not installed"
    exit 1
fi

# Check if virtual environment should be used
if [ -d "venv" ]; then
    log "Activating virtual environment"
    source venv/bin/activate
fi

# Check if dependencies are installed
if ! python3 -c "import selenium" 2>/dev/null; then
    log "Warning: Dependencies may not be installed. Run: pip install -r requirements.txt"
fi

# Clean up old logs if they're too large (keep last 50MB)
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(wc -c < "$LOG_FILE")
    if [ $LOG_SIZE -gt 52428800 ]; then
        log "Rotating log file (size: $((LOG_SIZE / 1048576))MB)"
        tail -c 52428800 "$LOG_FILE" > "${LOG_FILE}.tmp"
        mv "${LOG_FILE}.tmp" "$LOG_FILE"
    fi
fi

# Check for lock file to prevent concurrent runs
LOCK_FILE="/tmp/followfeed_script.lock"
if [ -f "$LOCK_FILE" ]; then
    # Check if the process is still running
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        log "Another instance is already running (PID: $LOCK_PID). Exiting."
        exit 0
    else
        log "Removing stale lock file"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
echo $$ > "$LOCK_FILE"

# Cleanup function
cleanup() {
    log "Cleaning up..."
    rm -f "$LOCK_FILE"
}

# Register cleanup on exit
trap cleanup EXIT

# Run the main script
log "Executing main.py"
if python3 main.py 2>&1 | tee -a "$LOG_FILE"; then
    log "========================================="
    log "FollowFeed completed successfully"
    log "========================================="
    exit 0
else
    EXIT_CODE=$?
    log "========================================="
    log "FollowFeed failed with exit code: $EXIT_CODE"
    log "========================================="
    exit $EXIT_CODE
fi