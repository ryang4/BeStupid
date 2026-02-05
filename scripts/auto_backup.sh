#!/bin/bash
# Auto-backup script with locking, retry, and proper pull-before-push
#
# Features:
# - flock to prevent concurrent runs
# - Pull BEFORE push (prevents non-fast-forward)
# - 3 retry attempts with exponential backoff
# - Telegram notification on failure
#
# Usage: Run this script at the end of each conversation session

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(dirname "$SCRIPT_DIR")}"
LOCK_FILE="${PROJECT_ROOT}/.git/backup.lock"
LOG_FILE="${PROJECT_ROOT}/logs/backup-failures.log"
MAX_RETRIES=3
RETRY_DELAY=5

cd "$PROJECT_ROOT"

# Note: Do NOT set GIT_CONFIG_GLOBAL=/dev/null - it breaks SSH credential lookup
# Instead, we use -c safe.directory in git_cmd() for Docker volume ownership issues

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

notify_failure() {
    local error_msg="$1"
    log "ERROR: $error_msg"

    # Log to file
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $error_msg" >> "$LOG_FILE"

    # Send Telegram notification
    if [[ -f "$SCRIPT_DIR/notify_backup_failure.py" ]]; then
        python3 "$SCRIPT_DIR/notify_backup_failure.py" "$error_msg" || true
    fi
}

git_cmd() {
    git -c safe.directory="$PROJECT_ROOT" \
        -c user.email="noreply@anthropic.com" \
        -c user.name="Claude Sonnet 4.5" \
        "$@"
}

# Retry function with exponential backoff
retry_with_backoff() {
    local cmd="$1"
    local delay=$RETRY_DELAY

    for attempt in $(seq 1 $MAX_RETRIES); do
        log "Attempt $attempt/$MAX_RETRIES: $cmd"

        if eval "$cmd"; then
            return 0
        fi

        if [[ $attempt -lt $MAX_RETRIES ]]; then
            log "Failed, retrying in ${delay}s..."
            sleep "$delay"
            delay=$((delay * 2))
        fi
    done

    return 1
}

do_backup() {
    # Check if there are changes to commit
    if ! git_cmd status --porcelain | grep -q '^'; then
        log "No changes to backup"
        return 0
    fi

    log "Changes detected, creating backup commit..."

    # Add all trackable changes
    git_cmd add content/ memory/ scripts/ .bestupid-private/ 2>/dev/null || true

    # Check if there's anything staged
    if ! git_cmd diff --cached --quiet 2>/dev/null; then
        # Create commit with timestamp
        TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
        if ! git_cmd commit -m "Auto-backup: $TIMESTAMP

Automated backup of conversation changes.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"; then
            notify_failure "Git commit failed at $TIMESTAMP"
            return 1
        fi
        log "✅ Backup commit created"
    else
        log "No staged changes to commit"
        return 0
    fi

    # CRITICAL: Pull BEFORE push to prevent non-fast-forward errors
    log "Pulling remote changes (rebase)..."
    if ! retry_with_backoff "git_cmd pull --rebase --autostash 2>&1"; then
        notify_failure "Git pull --rebase failed after $MAX_RETRIES attempts"
        # Don't fail here - local commit is still safe
        log "⚠️ Pull failed but local commit preserved"
    fi

    # Push to remote with retry
    log "Pushing to remote..."
    if retry_with_backoff "git_cmd push 2>&1"; then
        log "✅ Changes pushed to remote"
    else
        notify_failure "Git push failed after $MAX_RETRIES attempts"
        log "⚠️ Push failed - changes saved locally only"
        # Don't exit with error - the local commit succeeded
    fi
}

# Main execution with file locking
main() {
    # Ensure lock directory exists
    mkdir -p "$(dirname "$LOCK_FILE")"

    # Use flock to prevent concurrent runs
    exec 200>"$LOCK_FILE"
    if ! flock -n 200; then
        log "Another backup is already running, skipping"
        exit 0
    fi

    # Trap to release lock on exit
    trap 'rm -f "$LOCK_FILE"' EXIT

    do_backup
}

main "$@"
