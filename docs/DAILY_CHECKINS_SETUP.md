# Daily Check-ins Setup Guide

## Overview

Automated throughout-the-day check-ins to help you track:
- ☕ **10am**: Energy/focus levels + hydration
- 🍽️ **12pm**: Lunch logging
- 🚶 **3pm**: Movement reminder + energy boost
- 🍽️ **6pm**: Dinner logging + daily nutrition total
- 🌙 **10pm**: Sleep prep + log completion

These complement your existing:
- 7am morning briefing
- 9pm evening reminder

---

## Step 1: Test Check-ins Manually

Before scheduling, test each check-in:

```bash
cd /project

# Test mid-morning (10am)
python scripts/daily_checkins.py mid-morning

# Test lunch (12pm)
python scripts/daily_checkins.py lunch

# Test mid-afternoon (3pm)
python scripts/daily_checkins.py mid-afternoon

# Test dinner (6pm)
python scripts/daily_checkins.py dinner

# Test pre-bed (10pm)
python scripts/daily_checkins.py pre-bed
```

Each should send you a Telegram message immediately.

---

## Step 2: Schedule with Cron

Add these to your crontab:

```bash
crontab -e
```

Add the following lines (adjust paths as needed):

```cron
# Mid-morning check-in (10:00 AM)
0 10 * * * cd /project && python scripts/daily_checkins.py mid-morning >> /tmp/checkin-midmorning.log 2>&1

# Lunch check-in (12:00 PM)
0 12 * * * cd /project && python scripts/daily_checkins.py lunch >> /tmp/checkin-lunch.log 2>&1

# Mid-afternoon movement reminder (3:00 PM)
0 15 * * * cd /project && python scripts/daily_checkins.py mid-afternoon >> /tmp/checkin-midafternoon.log 2>&1

# Dinner check-in (6:00 PM)
0 18 * * * cd /project && python scripts/daily_checkins.py dinner >> /tmp/checkin-dinner.log 2>&1

# Pre-bed check-in (10:00 PM)
0 22 * * * cd /project && python scripts/daily_checkins.py pre-bed >> /tmp/checkin-prebed.log 2>&1
```

**Note**: If you're running in Docker, you'll need to set up cron inside the container or use a scheduler like Kubernetes CronJob.

---

## Step 3: Customize Timing

Edit times based on your schedule:

| Time | Purpose | Adjust if... |
|------|---------|--------------|
| 10am | Mid-morning energy check | You wake earlier/later |
| 12pm | Lunch reminder | You eat lunch at different time |
| 3pm | Movement break | Afternoon dip happens earlier/later |
| 6pm | Dinner logging | You eat dinner earlier/later |
| 10pm | Sleep prep | You go to bed earlier/later |

**Example**: If you wake at 5am and go to bed at 9pm:
- Change 10am → 8am
- Change 10pm → 9pm

---

## What Each Check-in Does

### Mid-Morning (10am)
- Checks if you've logged energy/focus
- Reminds you to hydrate
- Prompts to log current state if missing

### Lunch (12pm)
- Shows calories/protein so far
- Prompts you to log lunch meal
- Warns if calories are low

### Mid-Afternoon (3pm)
- Movement reminder (stretch, walk, squats)
- Warns against excess caffeine
- Suggests healthy energy boosts

### Dinner (6pm)
- Shows daily nutrition totals
- Calculates remaining calorie/protein targets
- Reminds you to finish eating by 8pm for better sleep

### Pre-Bed (10pm)
- Lists any missing log entries
- Shows final nutrition totals
- Sleep prep checklist
- Reminds you to set tomorrow's top 3

---

## Nutrition Targets

The system uses these defaults for a 245lb athlete:
- **Calories**: ~2500/day
- **Protein**: ~180g/day (0.73g per lb bodyweight)

To adjust, edit `scripts/daily_checkins.py`:

```python
# Around line 175
cal_remaining = 2500 - calories  # Change 2500
protein_remaining = 180 - protein  # Change 180
```

---

## Responding to Check-ins

**You can reply directly to any check-in message** and the bot will log it to your daily log (if integrated with telegram bot conversation handler).

Example responses:
- "Energy 7/10, focus 8/10"
- "Chicken bowl - 600 cal, 45g protein"
- "Feeling tired, took a 20min walk"

---

## Disable Specific Check-ins

If any check-in feels too frequent, comment it out in crontab:

```bash
crontab -e
```

Add `#` to disable:

```cron
# 0 15 * * * ...  # Mid-afternoon disabled
```

Or delete the line entirely.

---

## Troubleshooting

### Check-in not arriving

1. **Check logs**:
```bash
tail -f /tmp/checkin-lunch.log
```

2. **Test manually**:
```bash
python scripts/daily_checkins.py lunch
```

3. **Verify cron is running**:
```bash
crontab -l  # List all cron jobs
ps aux | grep cron  # Check cron daemon
```

### Wrong nutrition totals

The script parses your daily log's "Fuel Log" section:
```markdown
## Fuel Log
calories_so_far:: 1200
protein_so_far:: 85
```

Make sure this format is consistent in your logs.

---

## Files Created

- `scripts/daily_checkins.py` - Main check-in script
- `docs/DAILY_CHECKINS_SETUP.md` - This guide

---

## Complete Daily Schedule

With all notifications enabled:

| Time | Type | Purpose |
|------|------|---------|
| 7:00 AM | Morning Briefing | Recovery, workout, schedule, priorities |
| 10:00 AM | Mid-Morning | Energy check + hydration |
| 12:00 PM | Lunch | Meal logging |
| 3:00 PM | Mid-Afternoon | Movement + energy boost |
| 6:00 PM | Dinner | Meal logging + daily totals |
| 9:00 PM | Evening Reminder | Completion summary + tomorrow preview |
| 10:00 PM | Pre-Bed | Sleep prep + final log check |

**That's 7 touchpoints/day to keep you on track!**

---

## Next Steps

1. ✅ Test all 5 check-ins manually
2. ✅ Add to crontab with your preferred times
3. ✅ Adjust nutrition targets if needed
4. ✅ Monitor for 1 week and adjust timing/frequency

The goal: **Effortless tracking without manual logging friction.**

---

Generated: 2026-01-29
