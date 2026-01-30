#!/bin/bash
# Setup End-of-Day Reminder Cron Job
#
# This script sets up a daily reminder at 9 PM to fill in your daily log data.
#
# Usage: bash scripts/setup_eod_reminder.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Setting up end-of-day reminder cron job..."
echo "Project root: $PROJECT_ROOT"

# Create cron entry for 9 PM daily
CRON_JOB="0 21 * * * cd $PROJECT_ROOT && python3 scripts/end_of_day_reminder.py >> /tmp/eod_reminder.log 2>&1"

# Add to crontab (removes duplicates first)
(crontab -l 2>/dev/null | grep -v "end_of_day_reminder"; echo "$CRON_JOB") | crontab -

if [ $? -eq 0 ]; then
    echo "✅ Cron job added successfully!"
    echo ""
    echo "The reminder will run daily at 9:00 PM"
    echo ""
    echo "To verify, run: crontab -l"
    echo "To view logs: tail -f /tmp/eod_reminder.log"
    echo ""
    echo "To change the time, edit the cron schedule:"
    echo "  0 21 = 9:00 PM"
    echo "  0 22 = 10:00 PM"
    echo "  30 20 = 8:30 PM"
    echo "  etc."
else
    echo "❌ Failed to add cron job"
    exit 1
fi
