#!/bin/bash
set -e

HOME_DIR="$HOME"

# Write git config (mounted .gitconfig may be read-only)
cat "${HOME_DIR}/.gitconfig-mount" > "${HOME_DIR}/.gitconfig" 2>/dev/null || true
git config --global --add safe.directory /project

# Copy mounted SSH keys to a writable location with correct ownership
if [ -d "${HOME_DIR}/.ssh-mount" ]; then
    mkdir -p "${HOME_DIR}/.ssh"
    cp "${HOME_DIR}/.ssh-mount"/* "${HOME_DIR}/.ssh/" 2>/dev/null || true
    chmod 700 "${HOME_DIR}/.ssh"
    chmod 600 "${HOME_DIR}/.ssh"/id_* "${HOME_DIR}/.ssh"/config 2>/dev/null || true
    chmod 644 "${HOME_DIR}/.ssh"/*.pub 2>/dev/null || true
fi

exec "$@"
