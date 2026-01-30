# Backup Failure Notification System

## Overview

Automatic backup system with Telegram alerts on failure to prevent data loss.

## Components

### 1. Auto Backup Script (`auto_backup.sh`)
- Automatically commits changes in `content/`, `memory/`, `scripts/`
- Attempts to push to remote
- **Sends Telegram alert if commit or push fails**

### 2. Post-Commit Hook (`.git/hooks/post-commit`)
- Automatically triggers after commits with "Auto-backup", "Auto-generate", or "daily log" in message
- Attempts to push to remote
- **Sends Telegram alert if push fails**

### 3. Failure Notification (`notify_backup_failure.py`)
- Sends urgent Telegram message when backup fails
- Logs failures to `logs/backup-failures.log`
- Includes error details and recovery instructions

### 4. Backup Wrapper (`run_with_backup.sh`)
- Wraps any command with automatic backup
- Notifies on command failure
- Usage: `bash scripts/run_with_backup.sh "python scripts/daily_planner.py"`

## How It Works

```
[File Change]
    ↓
[auto_backup.sh runs]
    ↓
[Commit succeeds?] → NO → 🚨 Telegram Alert + Log
    ↓ YES
[Push succeeds?] → NO → 🚨 Telegram Alert + Log
    ↓ YES
✅ All backed up
```

## Alert Format

```
🚨 BACKUP FAILURE ALERT

Time: 2026-01-30 14:32:15
Error: Git push failed: Host key verification failed

⚠️ Changes may not be saved to remote!

Action required:
1. Check git status
2. Manually commit/push if needed
3. Verify SSH keys or GitHub token

Run: git status && git push
```

## Failure Scenarios Covered

1. ✅ Commit fails (file permissions, git config)
2. ✅ Push fails (SSH keys, network, credentials)
3. ✅ Command fails (script errors, crashes)
4. ✅ Telegram notification fails (logged to file as backup)

## Manual Testing

```bash
# Test notification system
python3 scripts/notify_backup_failure.py "Test message"

# Test auto backup
bash scripts/auto_backup.sh

# Test with wrapper
bash scripts/run_with_backup.sh "echo 'test' > test.txt"
```

## Recovery

If you receive an alert:

1. **Check what's uncommitted:**
   ```bash
   git status
   ```

2. **View recent changes:**
   ```bash
   git diff
   ```

3. **Manually backup:**
   ```bash
   git add .
   git commit -m "Manual backup after failure"
   git push
   ```

4. **Check failure log:**
   ```bash
   cat logs/backup-failures.log
   ```

## Configuration

Telegram credentials loaded from `telegram-bot/.env`:
- `TELEGRAM_BOT_TOKEN`
- `OWNER_CHAT_ID`

If these are missing, notifications will only log to file.

## Integration with GitHub Actions

GitHub Actions workflows also commit/push changes:
- `daily-planner.yml` (5 AM daily log generation)
- `morning-briefing.yml` (7 AM notification)
- `evening-reminder.yml` (9 PM notification)

These use GitHub's infrastructure and don't need this notification system.

## When Notifications Trigger

**You'll get alerted when:**
- Claude makes changes but can't commit them
- Commits succeed but push fails (SSH/auth issues)
- Automated scripts fail during execution
- Any git operation fails during backup

**You won't get alerted for:**
- Successful backups (silent success)
- GitHub Actions failures (check Actions tab)
- Manual git commands you run

---

**Last Updated:** 2026-01-30
