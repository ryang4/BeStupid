#!/bin/bash
# Auto-backup script to commit changes after each conversation
# Usage: Run this script at the end of each conversation session

cd /project

# Configure git to handle dubious ownership
export GIT_CONFIG_GLOBAL=/dev/null

# Check if there are changes to commit
if git -c safe.directory=/project status --porcelain | grep -q '^'; then
    echo "Changes detected, creating backup commit..."

    # Add all changes in content/, memory/, and scripts/
    git -c safe.directory=/project add content/ memory/ scripts/ 2>/dev/null || true

    # Create commit with timestamp
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    git -c safe.directory=/project \
        -c user.email="noreply@anthropic.com" \
        -c user.name="Claude Sonnet 4.5" \
        commit -m "Auto-backup: $TIMESTAMP

Automated backup of conversation changes.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

    echo "✅ Backup commit created"

    # Push to remote
    echo "Pushing to remote..."
    if git -c safe.directory=/project push 2>&1; then
        echo "✅ Changes pushed to remote"
    else
        echo "⚠️  Push failed - check git remote configuration"
    fi
else
    echo "No changes to backup"
fi
