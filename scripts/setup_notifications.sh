#!/bin/bash
# Setup all notification cron jobs

echo "Setting up daily notification cron jobs..."
echo ""

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "⚠️  Detected Docker environment"
    echo "Cron jobs need to be set up on the HOST machine, not in the container."
    echo ""
    echo "Please run this command on your HOST machine:"
    echo ""
    echo "crontab -e"
    echo ""
    echo "Then add these lines:"
    echo ""
    cat <<'EOF'
# Morning briefing at 7:00 AM
0 7 * * * cd /path/to/BeStupid && python telegram-bot/send_notification.py morning >> /tmp/morning-briefing.log 2>&1

# Mid-morning check-in at 10:00 AM
0 10 * * * cd /path/to/BeStupid && python scripts/daily_checkins.py mid-morning >> /tmp/checkin-midmorning.log 2>&1

# Lunch check-in at 12:00 PM
0 12 * * * cd /path/to/BeStupid && python scripts/daily_checkins.py lunch >> /tmp/checkin-lunch.log 2>&1

# Mid-afternoon check-in at 3:00 PM
0 15 * * * cd /path/to/BeStupid && python scripts/daily_checkins.py mid-afternoon >> /tmp/checkin-midafternoon.log 2>&1

# Dinner check-in at 6:00 PM
0 18 * * * cd /path/to/BeStupid && python scripts/daily_checkins.py dinner >> /tmp/checkin-dinner.log 2>&1

# Evening reminder at 9:00 PM
0 21 * * * cd /path/to/BeStupid && python telegram-bot/send_notification.py evening >> /tmp/evening-reminder.log 2>&1

# Pre-bed check-in at 10:00 PM
0 22 * * * cd /path/to/BeStupid && python scripts/daily_checkins.py pre-bed >> /tmp/checkin-prebed.log 2>&1
EOF
    echo ""
    echo "⚠️  Make sure to replace '/path/to/BeStupid' with your actual project path!"
    echo ""
    exit 1
fi

# Not in Docker - proceed with cron setup
echo "Adding cron jobs..."

# Create temporary cron file
TMPFILE=$(mktemp)

# Get existing crontab (if any)
crontab -l > "$TMPFILE" 2>/dev/null || true

# Check if our jobs already exist
if grep -q "BeStupid.*send_notification.py morning" "$TMPFILE"; then
    echo "⚠️  Notification cron jobs already exist!"
    echo "Remove them first with: crontab -e"
    rm "$TMPFILE"
    exit 1
fi

# Add our cron jobs
cat >> "$TMPFILE" <<EOF

# BeStupid Daily Notifications (added $(date '+%Y-%m-%d'))
0 7 * * * cd $PWD && python telegram-bot/send_notification.py morning >> /tmp/morning-briefing.log 2>&1
0 10 * * * cd $PWD && python scripts/daily_checkins.py mid-morning >> /tmp/checkin-midmorning.log 2>&1
0 12 * * * cd $PWD && python scripts/daily_checkins.py lunch >> /tmp/checkin-lunch.log 2>&1
0 15 * * * cd $PWD && python scripts/daily_checkins.py mid-afternoon >> /tmp/checkin-midafternoon.log 2>&1
0 18 * * * cd $PWD && python scripts/daily_checkins.py dinner >> /tmp/checkin-dinner.log 2>&1
0 21 * * * cd $PWD && python telegram-bot/send_notification.py evening >> /tmp/evening-reminder.log 2>&1
0 22 * * * cd $PWD && python scripts/daily_checkins.py pre-bed >> /tmp/checkin-prebed.log 2>&1
EOF

# Install new crontab
crontab "$TMPFILE"
rm "$TMPFILE"

echo "✅ Cron jobs installed!"
echo ""
echo "Your daily notification schedule:"
echo "  7:00 AM - Morning briefing"
echo " 10:00 AM - Mid-morning check-in"
echo " 12:00 PM - Lunch check-in"
echo "  3:00 PM - Mid-afternoon check-in"
echo "  6:00 PM - Dinner check-in"
echo "  9:00 PM - Evening reminder"
echo " 10:00 PM - Pre-bed check-in"
echo ""
echo "To view: crontab -l"
echo "To edit: crontab -e"
echo ""
echo "Logs will be written to /tmp/checkin-*.log and /tmp/*-briefing.log"
