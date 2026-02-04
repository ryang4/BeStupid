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
    git -c safe.directory=/project add content/ memory/ scripts/ .bestupid-private/ 2>/dev/null || true

    # Create commit with timestamp
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    if git -c safe.directory=/project \
        -c user.email="noreply@anthropic.com" \
        -c user.name="Claude Sonnet 4.5" \
        commit -m "Auto-backup: $TIMESTAMP

Automated backup of conversation changes.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>" 2>&1; then
        echo "✅ Backup commit created"
    else
        echo "❌ Commit failed!"
        python3 scripts/notify_backup_failure.py "Git commit failed at $TIMESTAMP"
        exit 1
    fi

    # Pull any remote changes first (e.g., from GitHub Actions)
    # Use --autostash to handle unstaged changes that might block the rebase
    echo "Pulling remote changes..."
    git -c safe.directory=/project pull --rebase --autostash 2>&1 || true

    # Push to remote
    echo "Pushing to remote..."
    PUSH_OUTPUT=$(git -c safe.directory=/project push 2>&1)
    PUSH_EXIT_CODE=$?

    if [ $PUSH_EXIT_CODE -eq 0 ]; then
        echo "✅ Changes pushed to remote"
    else
        echo "⚠️  Push failed - check git remote configuration"
        echo "Push error: $PUSH_OUTPUT"
        python3 scripts/notify_backup_failure.py "Git push failed: $PUSH_OUTPUT"
        # Don't exit on push failure - commit was successful
    fi
else
    echo "No changes to backup"
fi
