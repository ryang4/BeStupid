# Quick Reference - Life Optimization Commands

## 📊 Dashboard & Status

```bash
# Complete overview
python scripts/brain.py

# Compact view
python scripts/brain.py --compact

# Smart nudges
python scripts/notifications.py

# Critical alerts only
python scripts/notifications.py --critical
```

## 💪 Recovery & Training

```bash
# Sync Garmin data
python scripts/garmin_sync.py --days 7

# Latest recovery metrics
python scripts/garmin_sync.py --recovery

# Training recommendations
python scripts/garmin_sync.py --recovery | grep -A5 "Recommendations"
```

## 📅 Calendar

```bash
# Today's schedule
python scripts/calendar_sync.py

# This week
python scripts/calendar_sync.py --week

# Free time blocks
python scripts/calendar_sync.py --free

# Find training window (60min)
python scripts/calendar_sync.py --training 60
```

## 👥 Relationships (CRM)

```bash
# Show summary
python scripts/crm.py

# Add contact
python scripts/crm.py add

# Log interaction
python scripts/crm.py log "Name"

# Overdue follow-ups
python scripts/crm.py overdue

# Upcoming birthdays
python scripts/crm.py birthdays

# Contact details
python scripts/crm.py show "Name"
```

## 💰 Finance

```bash
# Dashboard
python scripts/finance.py

# Log business metrics
python scripts/finance.py business

# Log personal metrics
python scripts/finance.py personal

# Set goal
python scripts/finance.py goal "Goal Name" 50000 10000 "2026-12-31"

# Finance nudges
python scripts/finance.py nudges
```

## 🏥 Health

### Biomarkers
```bash
# Summary
python scripts/biomarkers.py

# Add lab test
python scripts/biomarkers.py add

# View trend
python scripts/biomarkers.py trend testosterone_total_ng_dl

# Nudges
python scripts/biomarkers.py nudges
```

### Supplements
```bash
# Current stack
python scripts/supplements.py

# Add supplement
python scripts/supplements.py add

# Log daily intake
python scripts/supplements.py log

# Compliance check
python scripts/supplements.py compliance

# Nudges
python scripts/supplements.py nudges
```

## 📝 Reviews & Goals

```bash
# Create quarterly review
python scripts/reviews.py create-quarter 2026-Q2

# Weekly check-in
python scripts/reviews.py check-in

# Active goals
python scripts/reviews.py goals

# Goal nudges
python scripts/reviews.py nudges
```

## 🧠 Decisions

```bash
# Log decision
python scripts/decisions.py log

# Review outcomes
python scripts/decisions.py review

# Pattern analysis
python scripts/decisions.py patterns
```

## 🔄 Daily Planning

```bash
# Generate today's log (runs at 5am automatically)
python scripts/daily_planner.py

# Generate weekly protocol
python scripts/weekly_planner.py

# Extract yesterday's metrics
python scripts/metrics_extractor.py
```

## 📱 Telegram Bot Commands

```
/brain              - Unified dashboard
/sync-garmin        - Sync wearable data
/calendar           - Today's schedule
/crm-overdue        - Overdue follow-ups
/finance            - Financial summary
/biomarkers         - Latest blood work
/supplements        - Stack & compliance
/nudges             - All smart notifications
/log-weight 182     - Quick metric update
/log-sleep 7.5      - Log sleep hours
/capture            - Add to inbox
/planday            - Regenerate today
/planweek           - Generate protocol
```

## 🎯 Common Workflows

### Morning Routine
```bash
# 1. Check dashboard
python scripts/brain.py --compact

# 2. Review nudges
python scripts/notifications.py --top 3

# 3. Open today's log
vim content/logs/$(date +%Y-%m-%d).md

# 4. Fill Quick Log section:
#    - Weight
#    - Sleep
#    - Sleep_Quality
#    - Mood_AM
#    - Energy
#    - Focus
```

### Log an Interaction
```bash
# Quick way
python scripts/crm.py log "John Doe"
# Then enter: type (call/email/meeting) and notes

# Or via Telegram
/log-interaction John Doe
```

### Check Recovery Before Training
```bash
# Get recovery score + recommendations
python scripts/garmin_sync.py --recovery

# If score < 50: consider rest day
# If score 50-70: moderate intensity
# If score > 70: can push hard
```

### Weekly Planning
```bash
# Sunday evening workflow
python scripts/weekly_planner.py    # Generate protocol
python scripts/reviews.py check-in  # OKR update
python scripts/crm.py overdue       # Who to reach out to
python scripts/calendar_sync.py --week  # Preview week
```

### Monthly Review
```bash
# First of month
python scripts/finance.py business      # Update metrics
python scripts/finance.py personal      # Personal finance
python scripts/supplements.py compliance # Check consistency
python scripts/crm.py overdue            # Relationship audit
python scripts/biomarkers.py             # Review trends
```

## 💾 Data Locations

**Public (in repo):**
- `data/daily_metrics.json`
- `data/garmin_metrics.json`
- `data/calendar_cache.json`

**Private (local only):**
- `~/.bestupid-private/relationships.json`
- `~/.bestupid-private/financial_metrics.json`
- `~/.bestupid-private/biomarkers.json`
- `~/.bestupid-private/supplements.json`
- `~/.bestupid-private/decisions.json`
- `~/.bestupid-private/inbox.md`

## 🔧 Setup Checklist

- [ ] Install dependencies: `pip install garminconnect google-auth-oauthlib google-api-python-client`
- [ ] Set up Garmin credentials (env vars or interactive login)
- [ ] Set up Google Calendar API (download credentials.json)
- [ ] Run first Garmin sync: `python scripts/garmin_sync.py --days 30`
- [ ] Run first calendar sync: `python scripts/calendar_sync.py`
- [ ] Add key relationships: `python scripts/crm.py add` (repeat for top 5-10)
- [ ] Log initial financial metrics: `python scripts/finance.py business && python scripts/finance.py personal`
- [ ] Set financial goals: `python scripts/finance.py goal "Goal" amount current deadline`
- [ ] Add supplement stack: `python scripts/supplements.py add` (for each supplement)
- [ ] Create quarterly review: `python scripts/reviews.py create-quarter 2026-Q1`
- [ ] Test brain dashboard: `python scripts/brain.py`
- [ ] Test smart nudges: `python scripts/notifications.py`

## 🚨 Troubleshooting

### Garmin sync failing
```bash
# Clear cached session
rm ~/.bestupid-private/garmin_session.json

# Re-auth
export GARMIN_EMAIL="your@email.com"
export GARMIN_PASSWORD="password"
python scripts/garmin_sync.py
```

### Calendar not syncing
```bash
# Re-authenticate
rm .google_token.pickle
python scripts/calendar_sync.py
```

### Data not showing in brain dashboard
```bash
# Check data files exist
ls -lh data/*.json
ls -lh ~/.bestupid-private/*.json

# Run initial sync for each system
python scripts/garmin_sync.py --days 7
python scripts/calendar_sync.py --cache
python scripts/finance.py
python scripts/crm.py
```

---

**Pro Tip:** Add aliases to your `.zshrc` or `.bashrc`:

```bash
# Brain aliases
alias brain='python ~/Projects/BeStupid/scripts/brain.py --compact'
alias nudges='python ~/Projects/BeStupid/scripts/notifications.py'
alias recovery='python ~/Projects/BeStupid/scripts/garmin_sync.py --recovery'
alias schedule='python ~/Projects/BeStupid/scripts/calendar_sync.py'
alias crm='python ~/Projects/BeStupid/scripts/crm.py'
alias finance='python ~/Projects/BeStupid/scripts/finance.py'
```

Then just type `brain` or `nudges` from anywhere!
