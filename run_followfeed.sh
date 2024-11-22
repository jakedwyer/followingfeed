#!/bin/bash

# Set script directory
SCRIPT_DIR="/root/followfeed"
PYTHON_PATH="/root/followfeed/xfeed/bin/python"
LOG_FILE="/var/log/followfeed.log"

# Change to the script directory
cd $SCRIPT_DIR || exit 1

# Activate virtual environment
source "${SCRIPT_DIR}/xfeed/bin/activate"

# Run the Python script with absolute path
$PYTHON_PATH main.py >> $LOG_FILE 2>&1

# Deactivate virtual environment
deactivate