#!/bin/bash
set -e

HOME_DIR="/home/botuser"

# Ensure home dir ownership (may be off after volume mounts)
chown botuser:botuser "${HOME_DIR}" 2>/dev/null || true

# Write git config (mounted .gitconfig may be read-only)
cat "${HOME_DIR}/.gitconfig-mount" > "${HOME_DIR}/.gitconfig" 2>/dev/null || true
chown botuser:botuser "${HOME_DIR}/.gitconfig" 2>/dev/null || true
gosu botuser git config --global --add safe.directory /project 2>/dev/null || true

# Copy mounted SSH keys to a writable location with correct ownership
if [ -d "${HOME_DIR}/.ssh-mount" ]; then
    mkdir -p "${HOME_DIR}/.ssh"
    cp "${HOME_DIR}/.ssh-mount"/* "${HOME_DIR}/.ssh/" 2>/dev/null || true
    chown -R botuser:botuser "${HOME_DIR}/.ssh"
    chmod 700 "${HOME_DIR}/.ssh"
    chmod 600 "${HOME_DIR}/.ssh"/id_* "${HOME_DIR}/.ssh"/config 2>/dev/null || true
    chmod 644 "${HOME_DIR}/.ssh"/*.pub 2>/dev/null || true
fi

# Start cron daemon in background
cron 2>/dev/null || true

# Pass environment variables to cron by writing them to a file botuser's crontab can source
env | grep -E '^(TELEGRAM_BOT_TOKEN|OWNER_CHAT_ID|ANTHROPIC_API_KEY|PROJECT_ROOT|PATH|HOME|PYTHONUNBUFFERED)=' > /home/botuser/.cron_env 2>/dev/null || true
chown botuser:botuser /home/botuser/.cron_env 2>/dev/null || true

# Drop privileges and run the bot
exec gosu botuser "$@"
