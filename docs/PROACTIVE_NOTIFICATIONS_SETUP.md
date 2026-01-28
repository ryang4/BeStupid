# Proactive Telegram Notifications - Setup Guide

## Overview

Your BeStupid system now sends you two daily Telegram messages:
- **7:00 AM** - Morning briefing (recovery, workout, schedule, priorities)
- **9:00 PM** - Evening reminder (completion summary, metrics status, tomorrow preview)

---

## Step 1: Configure Telegram Credentials

You need to create a `.env` file with your Telegram bot credentials.

### Create the .env file

```bash
cd telegram-bot
cp .env.template .env
```

### Edit the .env file

Open `telegram-bot/.env` and add your credentials:

```bash
# Get from @BotFather on Telegram (if you haven't already)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Get from @userinfobot on Telegram
OWNER_CHAT_ID=123456789

# Your existing Anthropic API key
ANTHROPIC_API_KEY=sk-ant-...
```

**How to get credentials:**
1. **TELEGRAM_BOT_TOKEN**: Message @BotFather on Telegram, use `/mybots`, select your bot, then "API Token"
2. **OWNER_CHAT_ID**: Message @userinfobot on Telegram, it will reply with your chat ID

---

## Step 2: Test Notifications Manually

Before scheduling, test that notifications work:

### Test Morning Briefing

```bash
cd /Users/ryang4/Projects/BeStupid
python telegram-bot/send_notification.py morning
```

**Expected output:**
```
📤 Sending morning notification...
Timestamp: 2026-01-25 10:30:00
✅ Message sent successfully to chat 123456789
Morning briefing sent ✅
```

**Check Telegram:** You should receive a message like:

```
☀️ Good morning, Ryan!

💪 Recovery: 72/100 (good)
Sleep: 7.2h (score: 78)
HRV: 54 (BALANCED)
→ Ready for moderate intensity

📅 Today's Schedule:
Events today: 4
Next: Product sync at 10:00 (45min)
Deep work: 14:00-16:30 (150min)

⚡ Top 3 Priorities:
1. Follow up with Sarah (mentor) - 35d overdue
2. Deep work: ML course (goal: 80% → 90%)
3. Fill out today's log

🏋️ Workout: Tempo run (6x1km @ threshold)
```

### Test Evening Reminder

```bash
python telegram-bot/send_notification.py evening
```

**Expected output:**
```
📤 Sending evening notification...
Timestamp: 2026-01-25 21:00:00
✅ Message sent successfully to chat 123456789
Evening reminder sent ✅
```

**Check Telegram:** You should receive:

```
🌙 Evening Reflection

📊 Today's Progress:
✅ Todos: 6/8 completed (75%)
✅ Metrics filled: Weight, Sleep, Mood_AM, Energy, Focus
❌ Missing: Mood_PM, Training_Output

📅 Tomorrow Preview:
Rest day - 3 meetings, 2.5h deep work block available

📝 Before bed:
- Fill out Mood_PM
- Fill out Training_Output
- Set tomorrow's top 3 priorities

Sleep well! 😴
```

---

## Step 3: Schedule with Cron

Once manual testing works, schedule the messages to send automatically.

### Add Cron Jobs

```bash
crontab -e
```

Add these two lines at the end:

```cron
# Morning briefing at 7:00 AM every day
0 7 * * * cd /Users/ryang4/Projects/BeStupid && .venv/bin/python telegram-bot/send_notification.py morning >> /tmp/morning-briefing.log 2>&1

# Evening reminder at 9:00 PM every day
0 21 * * * cd /Users/ryang4/Projects/BeStupid && .venv/bin/python telegram-bot/send_notification.py evening >> /tmp/evening-reminder.log 2>&1
```

**Save and exit** (in vim: press `Esc`, then type `:wq` and press Enter)

### Verify Cron Jobs Are Active

```bash
crontab -l
```

You should see your two cron jobs listed.

---

## Step 4: Wait for First Scheduled Messages

- **Tomorrow at 7:00 AM** - You'll receive your first morning briefing
- **Tomorrow at 9:00 PM** - You'll receive your first evening reminder

---

## Troubleshooting

### Messages Not Arriving

**Check cron logs:**
```bash
# Morning briefing log
tail -f /tmp/morning-briefing.log

# Evening reminder log
tail -f /tmp/evening-reminder.log
```

**Common issues:**

1. **"Error: TELEGRAM_BOT_TOKEN not set"**
   - Check that `telegram-bot/.env` exists and has valid credentials

2. **"Failed to send message: 401"**
   - Your `TELEGRAM_BOT_TOKEN` is invalid or expired
   - Get a new token from @BotFather

3. **"Failed to send message: 400"**
   - Your `OWNER_CHAT_ID` is invalid
   - Verify with @userinfobot

4. **Cron job doesn't run**
   - Check cron is running: `ps aux | grep cron`
   - Verify paths are absolute (not relative)
   - Check logs: `grep CRON /var/log/system.log` (macOS)

### Test Cron Job Manually

You can test if cron would work by running the exact cron command:

```bash
cd /Users/ryang4/Projects/BeStupid && .venv/bin/python telegram-bot/send_notification.py morning
```

If this works but cron doesn't, it's usually a PATH or environment issue.

---

## Adjust Timing

To change when messages arrive, edit your crontab:

```bash
crontab -e
```

**Cron time format:** `minute hour day month weekday`

Examples:
- `0 6 * * *` - 6:00 AM daily
- `30 7 * * *` - 7:30 AM daily
- `0 22 * * *` - 10:00 PM daily
- `0 7 * * 1-5` - 7:00 AM weekdays only

---

## Disable Notifications

To stop notifications temporarily:

```bash
crontab -e
```

Comment out the lines by adding `#` at the start:

```cron
# 0 7 * * * cd /Users/ryang4/Projects/BeStupid && .venv/bin/python ...
# 0 21 * * * cd /Users/ryang4/Projects/BeStupid && .venv/bin/python ...
```

To permanently remove:

```bash
crontab -e
# Delete the two lines entirely
```

---

## What Data Gets Included

### Morning Briefing

- **Recovery**: From Garmin (HRV, sleep, Body Battery) via `scripts/garmin_sync.py`
- **Workout**: From today's log `content/logs/YYYY-MM-DD.md` (Planned Workout section)
- **Schedule**: From Google Calendar via `scripts/calendar_sync.py`
- **Priorities**: Top 3 from `scripts/notifications.py` smart nudge engine

### Evening Reminder

- **Todo Completion**: Counts `- [x]` vs `- [ ]` in today's log
- **Metrics Filled**: Checks Weight, Sleep, Mood_AM, Mood_PM, Energy, Focus, etc.
- **Tomorrow Preview**: From this week's protocol `content/config/protocol_YYYY-MM-DD.md`

---

## Dependencies

**All dependencies already installed:**
- `python-telegram-bot` ✅
- `requests` ✅ (for HTTP API calls)
- `python-dotenv` ✅

**No new installations needed.**

---

## Success Metrics

**After 1 Week:**
- ✅ 7 morning briefings delivered at 7am
- ✅ 7 evening reminders delivered at 9pm
- ✅ You review briefing before starting your day
- ✅ You fill out reflection before bed

**After 1 Month:**
- ✅ Daily log completion rate improves
- ✅ Morning planning becomes automatic
- ✅ Better recovery awareness before training
- ✅ More intentional priority setting

---

## Files Created

**New Files:**
- `telegram-bot/send_notification.py` - Notification sender script

**Modified Files:**
- `scripts/brain.py` - Added `get_morning_briefing_data()` and `get_evening_reflection_data()`

**Configuration:**
- `telegram-bot/.env` - Your Telegram credentials (you need to create this)
- User crontab - Two scheduled jobs for 7am and 9pm

---

## Next Steps

1. ✅ Create `telegram-bot/.env` with your credentials
2. ✅ Test `python telegram-bot/send_notification.py morning`
3. ✅ Test `python telegram-bot/send_notification.py evening`
4. ✅ Add cron jobs with `crontab -e`
5. ✅ Wait for tomorrow morning's first briefing!

---

Generated: 2026-01-25
