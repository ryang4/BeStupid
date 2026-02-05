# BeStupid Project - Claude Code Guide

This is Ryan's personal productivity system: a Telegram bot powered by Claude that manages logs, memory, schedules, and automated backups.

## Project Structure

```
BeStupid/
├── telegram-bot/           # Main bot application
│   ├── bot.py              # Telegram message handlers
│   ├── claude_client.py    # Anthropic API integration
│   ├── tools.py            # Tool implementations (file ops, cron, search)
│   ├── scheduler.py        # Background job scheduler
│   ├── heartbeat.py        # Health monitoring system
│   └── tests/              # Pytest test suite
├── scripts/
│   ├── auto_backup.sh      # Git backup with locking/retry
│   ├── notify_backup_failure.py  # Telegram alerts on failures
│   ├── daily_planner.py    # Generate daily logs
│   ├── memory.py           # People/facts/decisions storage
│   └── context_briefing.py # Generate context for new sessions
├── content/                # PUBLIC Hugo site content
│   ├── logs/               # Daily logs (public)
│   └── config/             # Weekly protocols
├── memory/                 # Private memory storage
└── .bestupid-private/      # Private data (cron config, history)
```

## Critical Rules

### 1. Atomic Writes (ALWAYS)
Never write files directly. Always use tmp+rename pattern:
```python
tmp = target_file.with_suffix(".tmp")
tmp.write_text(content)
tmp.rename(target_file)  # Atomic on POSIX
```

### 2. Git Operations
- ALWAYS pull before push (prevents non-fast-forward)
- Use flock for concurrent backup prevention
- Retry with exponential backoff on network failures
- Notify on failures via Telegram

### 3. Error Handling
- No bare `except:` clauses - always catch specific exceptions
- Log all errors with context
- Send Telegram alerts for critical failures
- Tool errors must be visible to user, not swallowed

### 4. Public vs Private Data
- `content/` is PUBLIC (deployed to ryan-galliher.com)
- `memory/` and `.bestupid-private/` are PRIVATE
- NEVER write sensitive data to `content/`

### 5. File Locking
Use fcntl for log file appends:
```python
import fcntl
with open(log_file, "a") as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    try:
        f.write(entry)
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

## Testing

```bash
cd telegram-bot
pytest                  # Run all tests
pytest -v               # Verbose
pytest -k "atomic"      # Run specific tests
```

### Key Test Files
- `test_atomic_writes.py` - Verify crash-safe writes
- `test_git_backup.py` - Locking, retry, pull-before-push
- `test_scheduler.py` - Job loading and isolation
- `test_heartbeat.py` - Health monitoring
- `test_error_handling.py` - Error visibility
- `test_tools.py` - Tool implementations

## Deployment

### Docker (Primary)
```bash
cd telegram-bot
docker-compose up -d --build
docker-compose logs -f
docker-compose restart
```

### Health Monitoring
- Bot sends hourly heartbeat to owner
- Startup notification on launch
- `/health` command shows status
- Docker health check monitors heartbeat file

### Environment Variables
```
TELEGRAM_BOT_TOKEN=...
OWNER_CHAT_ID=...
ANTHROPIC_API_KEY=...
PROJECT_ROOT=/project
HISTORY_DIR=/project/.bestupid-private
```

## Common Tasks

### Add a new tool
1. Add tool definition to `TOOLS` list in `tools.py`
2. Add handler in `execute_tool()` dispatcher
3. Implement the function with proper error handling
4. Add tests in `test_tools.py`

### Debug backup failures
```bash
cat logs/backup-failures.log
tail -f logs/backup-failures.log
```

### Check scheduled jobs
Ask bot: "Get system status"
Or use `/health` command

### Reset conversation history
Delete `.bestupid-private/conversation_history.json`

## Architecture Decisions

### Why Python scheduler instead of cron?
- Survives container restarts
- Hot-reloadable via `reload_jobs()`
- Better error handling and logging
- Job crash isolation

### Why heartbeat over external monitoring?
- No external dependencies
- Self-contained in bot
- Direct Telegram integration
- Simple file-based external check option

### Why atomic writes everywhere?
- Prevents data corruption on crash/power loss
- Especially critical for cron_jobs.json
- Small overhead, big reliability win
