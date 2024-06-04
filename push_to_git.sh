#!/bin/bash

# Change to the directory containing the repository
cd /root/followfeed

# Stage changes
git add .

# Commit changes with a timestamp
commit_message="Automated commit on $(date '+%Y-%m-%d %H:%M:%S') following Cron Run to update outputs"
git commit -m "$commit_message"

# Push changes to the remote repository
git push