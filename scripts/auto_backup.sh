#!/bin/bash
# Auto-backup script - now uses robust Python backup
# This is a simple wrapper to the robust_git_backup.py script

cd /project

echo "Running robust git backup..."

if python3 scripts/robust_git_backup.py; then
    echo "✅ Backup completed successfully"
    exit 0
else
    echo "❌ Backup failed"
    # Still try to notify
    if [[ -f "scripts/notify_backup_failure.py" ]]; then
        python3 scripts/notify_backup_failure.py "Robust backup script failed" || true
    fi
    exit 1
fi