#!/usr/bin/env python3
"""
Set up bi-weekly content calendar for technical posts
"""
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

# Content calendar configuration
PRIVATE_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))
CONTENT_CALENDAR = PRIVATE_DIR / "content_calendar.json"

def create_content_calendar():
    """Create a content calendar with Tuesday/Friday posting schedule"""
    
    # Start from today
    start_date = datetime.now()
    
    # Find next Tuesday
    days_until_tuesday = (1 - start_date.weekday()) % 7
    if days_until_tuesday == 0 and start_date.weekday() == 1:
        next_tuesday = start_date
    else:
        next_tuesday = start_date + timedelta(days=days_until_tuesday)
    
    # Generate 8 weeks of Tuesday/Friday schedule
    calendar = {
        "version": "1.0",
        "schedule": "Tuesday and Friday",
        "habit_type": "technical_content",
        "target_per_week": 2,
        "upcoming_deadlines": []
    }
    
    current_date = next_tuesday
    for week in range(8):
        # Tuesday post
        tuesday = current_date + timedelta(weeks=week)
        calendar["upcoming_deadlines"].append({
            "date": tuesday.strftime("%Y-%m-%d"),
            "day": "Tuesday",
            "type": "Technical Post #1",
            "status": "scheduled",
            "ideas": []
        })
        
        # Friday post
        friday = tuesday + timedelta(days=3)
        calendar["upcoming_deadlines"].append({
            "date": friday.strftime("%Y-%m-%d"),
            "day": "Friday", 
            "type": "Technical Post #2",
            "status": "scheduled",
            "ideas": []
        })
    
    # Add content ideas based on recent work
    calendar["content_ideas"] = [
        "AWS deployment debugging walkthrough",
        "Docker container optimization techniques",
        "Staging environment setup guide",
        "Cold Turkey productivity setup tutorial",
        "Telegram bot automation for developers",
        "Git backup strategies for containers",
        "'Think step by step' prompt engineering",
        "Swimming technique progress tracking",
        "Focus system design for developers",
        "Claude Code efficiency tips"
    ]
    
    # Ensure directory exists
    CONTENT_CALENDAR.parent.mkdir(parents=True, exist_ok=True)
    
    # Write calendar
    with open(CONTENT_CALENDAR, 'w') as f:
        json.dump(calendar, f, indent=2)
    
    print("✅ Content calendar created!")
    print(f"📅 Schedule: Every Tuesday and Friday")
    print(f"📍 Next Tuesday: {next_tuesday.strftime('%Y-%m-%d')}")
    print(f"📍 Next Friday: {(next_tuesday + timedelta(days=3)).strftime('%Y-%m-%d')}")
    
    return calendar

def show_upcoming_deadlines():
    """Show next few deadlines"""
    if not CONTENT_CALENDAR.exists():
        print("No content calendar found. Run create_content_calendar() first.")
        return
    
    with open(CONTENT_CALENDAR) as f:
        calendar = json.load(f)
    
    print("\n📅 Upcoming Content Deadlines:")
    today = datetime.now().date()
    
    upcoming = []
    for deadline in calendar["upcoming_deadlines"]:
        deadline_date = datetime.strptime(deadline["date"], "%Y-%m-%d").date()
        if deadline_date >= today:
            days_away = (deadline_date - today).days
            upcoming.append((days_away, deadline))
    
    # Sort by days away and show next 6
    upcoming.sort()
    for i, (days_away, deadline) in enumerate(upcoming[:6]):
        status_emoji = "📝" if days_away <= 2 else "📅"
        urgency = f"({days_away} days)" if days_away > 0 else "(TODAY!)"
        print(f"{status_emoji} {deadline['day']} {deadline['date']}: {deadline['type']} {urgency}")

def main():
    calendar = create_content_calendar()
    show_upcoming_deadlines()
    
    print("\n💡 Content Ideas Available:")
    for idea in calendar["content_ideas"][:5]:
        print(f"  • {idea}")
    print(f"  ... and {len(calendar['content_ideas']) - 5} more ideas")
    
    print("\n🔄 To view upcoming deadlines anytime:")
    print("python scripts/setup_content_calendar.py --show")

if __name__ == "__main__":
    import sys
    if "--show" in sys.argv:
        show_upcoming_deadlines()
    else:
        main()