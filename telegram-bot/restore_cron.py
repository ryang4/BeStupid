#!/usr/bin/env python3
"""Restore enabled cron jobs from config on container start."""

import json
import subprocess
from pathlib import Path

CRON_CONFIG = Path.home() / ".bestupid-private" / "cron_jobs.json"
ENV_SOURCE = ". /home/botuser/.cron_env; "

ALLOWED_CRON_COMMANDS = {
    "morning_briefing": "cd /project && python telegram-bot/send_notification.py morning",
    "evening_reminder": "cd /project && python telegram-bot/send_notification.py evening",
    "daily_planner": "cd /project && python scripts/daily_planner.py",
    "auto_backup": "cd /project && bash scripts/auto_backup.sh",
}

if not CRON_CONFIG.exists():
    raise SystemExit(0)

config = json.loads(CRON_CONFIG.read_text())
lines = []
for name, entry in config.items():
    if name in ALLOWED_CRON_COMMANDS and entry.get("enabled"):
        cmd = ALLOWED_CRON_COMMANDS[name]
        lines.append(f"{entry['schedule']} {ENV_SOURCE}{cmd}")

crontab = "\n".join(lines) + "\n" if lines else ""
subprocess.run(["crontab", "-"], input=crontab, text=True, check=True)
