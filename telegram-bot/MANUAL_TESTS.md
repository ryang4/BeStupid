# Manual Test Scenarios

These tests validate the bot's behavior through actual interaction. Run them after deployment or significant changes.

## Prerequisites
- Bot is running (`docker-compose up -d`)
- You have access to the owner chat
- Wait 30 seconds after start for initialization

---

## Test 1: Cron Persistence

**Purpose:** Verify cron jobs survive container restarts

**Steps:**
1. Ask bot: "Add a cron job for 8am daily test"
2. Wait for confirmation
3. Ask: "List cron jobs" - verify job is listed
4. Run: `docker-compose restart`
5. Wait for bot startup message
6. Ask: "List cron jobs"

**Expected:** Job still exists after restart

**Pass Criteria:** Job appears in list both before and after restart

---

## Test 2: Backup Status

**Purpose:** Verify backup failure logging and visibility

**Steps:**
1. Ask bot: "Get system status"
2. Or ask: "What's my backup status?"

**Expected:**
- Shows git branch and commit
- Shows recent backup failures (if any)
- Shows scheduled jobs

**Pass Criteria:** Status displays without errors, shows relevant info

---

## Test 3: Error Visibility

**Purpose:** Verify errors are visible, not swallowed

**Steps:**
1. Ask bot: "Run script /nonexistent_script_xyz.py"
2. Observe response

**Expected:**
- Clear error message about script not found
- NOT a silent failure or generic "error"

**Pass Criteria:** Error message is specific and actionable

---

## Test 4: Large Output Truncation

**Purpose:** Verify truncation warning appears

**Steps:**
1. Ask bot: "Read the entire tools.py file"
2. Observe response

**Expected:**
- File content displayed
- Truncation warning if content exceeds limit
- Shows percentage truncated

**Pass Criteria:** If truncated, warning clearly shows "OUTPUT TRUNCATED: Showing X of Y chars"

---

## Test 5: System Health Command

**Purpose:** Verify health status reporting

**Steps:**
1. Send command: `/health`
2. Observe response

**Expected:**
- Uptime displayed
- Last activity time
- Pending jobs count
- Memory usage

**Pass Criteria:** All health metrics displayed

---

## Test 6: Heartbeat (Long-Running)

**Purpose:** Verify periodic health checks

**Steps:**
1. Note the time
2. Wait 1 hour (or check heartbeat.txt)
3. Check for heartbeat message

**Alternative (faster):**
```bash
cat .bestupid-private/heartbeat.txt
```

**Expected:**
- Heartbeat message received hourly
- Heartbeat file updated regularly

**Pass Criteria:** Heartbeat file exists and is recent

---

## Test 7: Startup Notification

**Purpose:** Verify bot announces when it starts

**Steps:**
1. Run: `docker-compose restart`
2. Watch chat for notification

**Expected:**
- Message: "BeStupid Bot Started"
- Shows startup time

**Pass Criteria:** Startup message received within 30 seconds

---

## Test 8: Concurrent Backup Prevention

**Purpose:** Verify only one backup runs at a time

**Steps:**
1. Open two terminals
2. Run simultaneously:
   ```bash
   bash scripts/auto_backup.sh &
   bash scripts/auto_backup.sh &
   ```
3. Observe output

**Expected:**
- One shows "Another backup is already running, skipping"
- One completes normally

**Pass Criteria:** Only one backup executes

---

## Test 9: Kill Mid-Write Recovery

**Purpose:** Verify atomic writes prevent corruption

**Steps:**
1. Check current cron config:
   ```bash
   cat .bestupid-private/cron_jobs.json
   ```
2. Start adding a cron job via bot
3. While processing, run:
   ```bash
   docker kill bestupid-telegram-bot
   ```
4. Restart: `docker-compose up -d`
5. Check cron config again

**Expected:**
- Config is either unchanged (operation didn't complete)
- Or config has new job (operation completed atomically)
- NEVER corrupted/partial JSON

**Pass Criteria:** Config file is valid JSON after crash

---

## Test 10: DNS Failure Recovery

**Purpose:** Verify git operations handle DNS issues

**Steps:**
1. Simulate DNS failure (if possible)
2. Ask bot to perform action that triggers backup
3. Check logs for retry attempts

**Alternative:** Check docker-compose.yml has DNS servers configured

**Expected:**
- Multiple retry attempts with backoff
- Fallback DNS servers available
- Failure notification if all retries fail

**Pass Criteria:** Retries visible in logs, notification sent on final failure

---

## Quick Smoke Test Checklist

Run these quickly after any deployment:

- [ ] `/start` works
- [ ] `/health` shows status
- [ ] "Get system status" returns info
- [ ] "Read today's log" works (or says log doesn't exist)
- [ ] "List cron jobs" works
- [ ] Startup notification received (if just restarted)

---

## Troubleshooting

### Bot not responding
```bash
docker-compose logs -f
docker-compose ps
```

### Backup failures
```bash
cat logs/backup-failures.log
```

### Health check failing
```bash
docker inspect bestupid-telegram-bot --format='{{.State.Health.Status}}'
cat .bestupid-private/heartbeat.txt
```

### Cron jobs not running
```bash
# Check config
cat .bestupid-private/cron_jobs.json

# Ask bot
"Get system status"
```
