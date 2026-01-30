#!/bin/bash
# Wrapper to run any script and auto-backup changes afterward
#
# Usage: bash scripts/run_with_backup.sh <command>
# Example: bash scripts/run_with_backup.sh "python scripts/daily_planner.py"

set -e  # Exit on error

COMMAND="$@"

if [ -z "$COMMAND" ]; then
    echo "Usage: bash scripts/run_with_backup.sh <command>"
    exit 1
fi

echo "Running: $COMMAND"
echo "---"

# Run the command
if eval "$COMMAND"; then
    echo "---"
    echo "✅ Command completed successfully"

    # Check if there are changes
    cd /project
    if git status --porcelain | grep -q '^'; then
        echo ""
        echo "Changes detected, running auto-backup..."
        bash scripts/auto_backup.sh
    else
        echo "No changes to backup"
    fi
else
    EXIT_CODE=$?
    echo "---"
    echo "❌ Command failed with exit code $EXIT_CODE"
    python3 scripts/notify_backup_failure.py "Command failed: $COMMAND (exit code $EXIT_CODE)"
    exit $EXIT_CODE
fi
