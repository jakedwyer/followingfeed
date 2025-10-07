#!/bin/bash
# CRITICAL: Remove 'aux' file with exposed secrets from git history

echo "⚠️  CRITICAL SECURITY FIX"
echo "This will remove the 'aux' file from ALL git history"
echo ""
echo "Files to be purged from history:"
echo "  - aux (contains exposed API keys and tokens)"
echo ""
read -p "Do you want to proceed? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted. Secrets are still in git history!"
    exit 1
fi

echo ""
echo "Creating backup..."
git branch backup-before-purge

echo ""
echo "Removing 'aux' from git history..."
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch aux" \
  --prune-empty --tag-name-filter cat -- --all

echo ""
echo "Cleaning up..."
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo ""
echo "✅ 'aux' file removed from git history"
echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "1. Verify the removal: git log --all -- aux"
echo "2. If pushed to remote: git push origin --force --all"
echo "3. ROTATE all exposed API keys immediately!"
echo ""
