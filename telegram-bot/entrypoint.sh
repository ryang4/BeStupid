#!/bin/bash
# Entrypoint for BeStupid Telegram Bot
# All setup runs as botuser to avoid macOS Docker permission issues

HOME_DIR="/home/botuser"

# Start cron daemon in background (requires root)
cron 2>/dev/null || true

# Switch to botuser for all remaining setup
exec gosu botuser bash -c '
HOME_DIR="/home/botuser"

# Merge mounted git config with safe.directory
if [ -f "${HOME_DIR}/.gitconfig-mount" ]; then
    cat "${HOME_DIR}/.gitconfig-mount" > "${HOME_DIR}/.gitconfig" 2>/dev/null || true
    git config --global --add safe.directory /project 2>/dev/null || true
fi

# Copy mounted SSH keys to a writable location
if [ -d "${HOME_DIR}/.ssh-mount" ]; then
    mkdir -p "${HOME_DIR}/.ssh"
    cp "${HOME_DIR}/.ssh-mount"/* "${HOME_DIR}/.ssh/" 2>/dev/null || true
    chmod 700 "${HOME_DIR}/.ssh" 2>/dev/null || true
    chmod 600 "${HOME_DIR}/.ssh"/id_* "${HOME_DIR}/.ssh"/config 2>/dev/null || true
    chmod 644 "${HOME_DIR}/.ssh"/*.pub 2>/dev/null || true
fi

# Save env vars for cron jobs
env | grep -E "^(TELEGRAM_BOT_TOKEN|OWNER_CHAT_ID|ANTHROPIC_API_KEY|PROJECT_ROOT|PATH|HOME|PYTHONUNBUFFERED|HISTORY_DIR)=" > "${HOME_DIR}/.cron_env" 2>/dev/null || true

# Restore persistent cron jobs from config
if [ -f "${HOME_DIR}/.bestupid-private/cron_jobs.json" ]; then
    python /app/restore_cron.py 2>/dev/null || true
fi

# Run the main command
exec "$@"
' -- "$@"
