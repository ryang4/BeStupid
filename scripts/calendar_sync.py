"""
Google Calendar Integration - Time blocking and scheduling intelligence.

Provides:
- Today's schedule overview
- Free time block detection
- Meeting preparation reminders
- Conflict detection with training schedule
- Time blocking recommendations for deep work

Requires:
- pip install google-auth-oauthlib google-api-python-client
- Google Calendar API credentials (credentials.json)

Usage:
    python calendar_sync.py              # Show today's schedule
    python calendar_sync.py --week       # Show week overview
    python calendar_sync.py --free       # Show free blocks today
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, List
import pickle
import argparse

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CALENDAR_DATA_FILE = os.path.join(PROJECT_ROOT, "data", "calendar_cache.json")
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, ".google_credentials.json")
TOKEN_FILE = os.path.join(PROJECT_ROOT, ".google_token.pickle")

# Google Calendar API scope (read-only by default)
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Work hours for free time calculation
WORK_START_HOUR = 8
WORK_END_HOUR = 18

# Minimum duration for a "free block" (minutes)
MIN_FREE_BLOCK_MINUTES = 30


def get_calendar_service():
    """
    Get authenticated Google Calendar service.

    Returns:
        Google Calendar API service object, or None if not configured
    """
    if not GOOGLE_AVAILABLE:
        print("Error: Google Calendar libraries not installed.")
        print("Run: pip install google-auth-oauthlib google-api-python-client")
        return None

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Error: Credentials file not found at {CREDENTIALS_FILE}")
        print("Download from Google Cloud Console and save as .google_credentials.json")
        return None

    creds = None

    # Load existing token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return build('calendar', 'v3', credentials=creds)


def fetch_events(start_date: datetime, end_date: datetime, calendar_id: str = 'primary') -> List[dict]:
    """
    Fetch calendar events for a date range.

    Args:
        start_date: Start of range
        end_date: End of range
        calendar_id: Google Calendar ID (default: primary)

    Returns:
        List of event dicts
    """
    service = get_calendar_service()
    if not service:
        return []

    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_date.isoformat() + 'Z',
            timeMax=end_date.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        return [
            {
                "id": e.get("id"),
                "title": e.get("summary", "No title"),
                "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date")),
                "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date")),
                "location": e.get("location", ""),
                "description": e.get("description", "")[:200] if e.get("description") else "",
                "attendees": [a.get("email") for a in e.get("attendees", [])],
                "is_all_day": "date" in e.get("start", {}),
                "status": e.get("status", "confirmed"),
                "creator": e.get("creator", {}).get("email", "")
            }
            for e in events
            if e.get("status") != "cancelled"
        ]

    except Exception as e:
        print(f"Error fetching events: {e}")
        return []


def get_todays_events() -> List[dict]:
    """Get all events for today."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    return fetch_events(today, tomorrow)


def get_weeks_events() -> List[dict]:
    """Get all events for the current week."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # Start from Monday
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=7)
    return fetch_events(monday, sunday)


def calculate_free_blocks(events: List[dict], date: datetime = None) -> List[dict]:
    """
    Calculate free time blocks between events.

    Args:
        events: List of events for the day
        date: Date to analyze (default: today)

    Returns:
        List of free block dicts with start, end, duration
    """
    if date is None:
        date = datetime.now()

    # Work hours for the day
    work_start = date.replace(hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
    work_end = date.replace(hour=WORK_END_HOUR, minute=0, second=0, microsecond=0)

    # Filter to non-all-day events and sort by start time
    timed_events = []
    for e in events:
        if e["is_all_day"]:
            continue
        try:
            start = datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(e["end"].replace("Z", "+00:00"))
            # Convert to local time (naive)
            start = start.replace(tzinfo=None)
            end = end.replace(tzinfo=None)
            timed_events.append({"start": start, "end": end, "title": e["title"]})
        except (ValueError, TypeError):
            continue

    timed_events.sort(key=lambda x: x["start"])

    free_blocks = []
    current_time = work_start

    for event in timed_events:
        event_start = max(event["start"], work_start)
        event_end = min(event["end"], work_end)

        if event_start > current_time:
            # There's a gap
            gap_minutes = (event_start - current_time).total_seconds() / 60
            if gap_minutes >= MIN_FREE_BLOCK_MINUTES:
                free_blocks.append({
                    "start": current_time.strftime("%H:%M"),
                    "end": event_start.strftime("%H:%M"),
                    "duration_minutes": int(gap_minutes),
                    "recommended_use": categorize_time_block(int(gap_minutes))
                })

        current_time = max(current_time, event_end)

    # Check for time after last event
    if current_time < work_end:
        gap_minutes = (work_end - current_time).total_seconds() / 60
        if gap_minutes >= MIN_FREE_BLOCK_MINUTES:
            free_blocks.append({
                "start": current_time.strftime("%H:%M"),
                "end": work_end.strftime("%H:%M"),
                "duration_minutes": int(gap_minutes),
                "recommended_use": categorize_time_block(int(gap_minutes))
            })

    return free_blocks


def categorize_time_block(minutes: int) -> str:
    """Categorize a time block by its ideal use."""
    if minutes >= 120:
        return "deep_work"
    elif minutes >= 60:
        return "focused_task"
    elif minutes >= 30:
        return "admin_or_quick_task"
    else:
        return "break"


def get_meeting_prep_reminders(events: List[dict]) -> List[dict]:
    """
    Generate meeting preparation reminders.

    Returns:
        List of prep reminder dicts for upcoming meetings
    """
    reminders = []
    now = datetime.now()

    for event in events:
        if event["is_all_day"]:
            continue

        try:
            start = datetime.fromisoformat(event["start"].replace("Z", "+00:00")).replace(tzinfo=None)
            minutes_until = (start - now).total_seconds() / 60

            # Only remind for meetings in next 2 hours
            if 0 < minutes_until <= 120:
                has_attendees = len(event.get("attendees", [])) > 1

                reminder = {
                    "event": event["title"],
                    "time": start.strftime("%H:%M"),
                    "minutes_until": int(minutes_until),
                    "location": event.get("location", ""),
                    "prep_items": []
                }

                if has_attendees:
                    reminder["prep_items"].append("Review attendee backgrounds")
                if event.get("description"):
                    reminder["prep_items"].append("Review meeting agenda")
                if event.get("location") and "http" in event.get("location", ""):
                    reminder["prep_items"].append("Test video/audio")
                elif event.get("location"):
                    reminder["prep_items"].append(f"Travel to {event['location']}")

                reminders.append(reminder)

        except (ValueError, TypeError):
            continue

    return reminders


def check_training_conflicts(training_time: str, training_duration: int = 60) -> List[dict]:
    """
    Check if proposed training time conflicts with calendar.

    Args:
        training_time: Proposed time in HH:MM format
        training_duration: Duration in minutes

    Returns:
        List of conflicting events
    """
    events = get_todays_events()
    conflicts = []

    try:
        today = datetime.now().date()
        hour, minute = map(int, training_time.split(":"))
        training_start = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
        training_end = training_start + timedelta(minutes=training_duration)

        for event in events:
            if event["is_all_day"]:
                continue

            try:
                event_start = datetime.fromisoformat(event["start"].replace("Z", "+00:00")).replace(tzinfo=None)
                event_end = datetime.fromisoformat(event["end"].replace("Z", "+00:00")).replace(tzinfo=None)

                # Check for overlap
                if not (training_end <= event_start or training_start >= event_end):
                    conflicts.append({
                        "event": event["title"],
                        "time": f"{event_start.strftime('%H:%M')}-{event_end.strftime('%H:%M')}",
                        "overlap_minutes": int(min(training_end, event_end).timestamp() -
                                               max(training_start, event_start).timestamp()) // 60
                    })
            except (ValueError, TypeError):
                continue

    except ValueError:
        pass

    return conflicts


def suggest_training_windows(duration: int = 60) -> List[dict]:
    """
    Suggest optimal windows for training based on calendar.

    Args:
        duration: Required training duration in minutes

    Returns:
        List of suggested time windows with scores
    """
    events = get_todays_events()
    free_blocks = calculate_free_blocks(events)

    # Filter blocks that can fit the training
    suitable = [b for b in free_blocks if b["duration_minutes"] >= duration]

    suggestions = []
    for block in suitable:
        start_hour = int(block["start"].split(":")[0])

        # Score based on time of day (prefer morning/evening for training)
        if 5 <= start_hour <= 8:
            score = 10  # Early morning - excellent
            reason = "Early morning - high energy, fewer interruptions"
        elif 11 <= start_hour <= 13:
            score = 7   # Lunch time - good
            reason = "Lunch break - natural break in day"
        elif 16 <= start_hour <= 18:
            score = 8   # Late afternoon - good
            reason = "End of work day - good transition"
        else:
            score = 5   # Other times
            reason = "Available slot"

        suggestions.append({
            "window": f"{block['start']}-{block['end']}",
            "available_minutes": block["duration_minutes"],
            "score": score,
            "reason": reason
        })

    suggestions.sort(key=lambda x: -x["score"])
    return suggestions


def get_schedule_summary() -> dict:
    """
    Get a summary of today's schedule for the daily briefing.

    Returns:
        dict with events, free blocks, next meeting, etc.
    """
    events = get_todays_events()
    free_blocks = calculate_free_blocks(events)
    prep_reminders = get_meeting_prep_reminders(events)

    # Find next meeting
    now = datetime.now()
    next_meeting = None
    for event in events:
        if event["is_all_day"]:
            continue
        try:
            start = datetime.fromisoformat(event["start"].replace("Z", "+00:00")).replace(tzinfo=None)
            if start > now:
                next_meeting = {
                    "title": event["title"],
                    "time": start.strftime("%H:%M"),
                    "minutes_until": int((start - now).total_seconds() / 60)
                }
                break
        except (ValueError, TypeError):
            continue

    # Calculate total meeting time
    total_meeting_minutes = 0
    for event in events:
        if event["is_all_day"]:
            continue
        try:
            start = datetime.fromisoformat(event["start"].replace("Z", "+00:00")).replace(tzinfo=None)
            end = datetime.fromisoformat(event["end"].replace("Z", "+00:00")).replace(tzinfo=None)
            total_meeting_minutes += (end - start).total_seconds() / 60
        except (ValueError, TypeError):
            continue

    # Calculate total free time
    total_free_minutes = sum(b["duration_minutes"] for b in free_blocks)

    # Find longest free block
    longest_block = max(free_blocks, key=lambda x: x["duration_minutes"]) if free_blocks else None

    return {
        "date": now.strftime("%Y-%m-%d"),
        "day": now.strftime("%A"),
        "total_events": len(events),
        "events": events,
        "total_meeting_hours": round(total_meeting_minutes / 60, 1),
        "total_free_hours": round(total_free_minutes / 60, 1),
        "free_blocks": free_blocks,
        "longest_free_block": longest_block,
        "next_meeting": next_meeting,
        "prep_reminders": prep_reminders,
        "deep_work_available": any(b["recommended_use"] == "deep_work" for b in free_blocks)
    }


def cache_schedule():
    """Cache today's schedule for offline access."""
    summary = get_schedule_summary()

    data_dir = os.path.dirname(CALENDAR_DATA_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    with open(CALENDAR_DATA_FILE, 'w') as f:
        json.dump({
            "cached_at": datetime.now().isoformat(),
            "schedule": summary
        }, f, indent=2)

    print(f"Schedule cached to {CALENDAR_DATA_FILE}")


def get_cached_schedule() -> Optional[dict]:
    """Get cached schedule if available and fresh."""
    if not os.path.exists(CALENDAR_DATA_FILE):
        return None

    try:
        with open(CALENDAR_DATA_FILE, 'r') as f:
            data = json.load(f)

        cached_at = datetime.fromisoformat(data["cached_at"])
        if (datetime.now() - cached_at).total_seconds() < 3600:  # 1 hour
            return data["schedule"]
    except Exception:
        pass

    return None


def format_schedule_for_display(summary: dict) -> str:
    """Format schedule summary as readable text."""
    lines = []
    lines.append(f"📅 Schedule for {summary['day']}, {summary['date']}")
    lines.append("")

    if summary["next_meeting"]:
        nm = summary["next_meeting"]
        lines.append(f"⏰ Next: {nm['title']} at {nm['time']} ({nm['minutes_until']} min)")
        lines.append("")

    lines.append(f"📊 Today: {summary['total_events']} events, {summary['total_meeting_hours']}h meetings")
    lines.append(f"💚 Free time: {summary['total_free_hours']}h available")

    if summary["longest_free_block"]:
        lb = summary["longest_free_block"]
        lines.append(f"🎯 Longest block: {lb['start']}-{lb['end']} ({lb['duration_minutes']}min)")

    if summary["deep_work_available"]:
        lines.append("✅ Deep work block available")
    else:
        lines.append("⚠️ No deep work blocks today")

    if summary["prep_reminders"]:
        lines.append("")
        lines.append("📝 Meeting Prep:")
        for prep in summary["prep_reminders"][:3]:
            lines.append(f"  - {prep['event']} in {prep['minutes_until']}min")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Calendar integration")
    parser.add_argument("--week", action="store_true", help="Show week overview")
    parser.add_argument("--free", action="store_true", help="Show free blocks")
    parser.add_argument("--cache", action="store_true", help="Cache schedule")
    parser.add_argument("--training", type=int, help="Suggest training windows (duration in min)")
    args = parser.parse_args()

    if args.cache:
        cache_schedule()
    elif args.free:
        events = get_todays_events()
        blocks = calculate_free_blocks(events)
        print("\n=== Free Time Blocks ===")
        for block in blocks:
            print(f"  {block['start']}-{block['end']}: {block['duration_minutes']}min ({block['recommended_use']})")
    elif args.training:
        suggestions = suggest_training_windows(args.training)
        print(f"\n=== Training Windows ({args.training}min) ===")
        for s in suggestions:
            print(f"  {s['window']}: Score {s['score']}/10 - {s['reason']}")
    elif args.week:
        events = get_weeks_events()
        print(f"\n=== Week Overview ({len(events)} events) ===")
        current_day = None
        for e in events:
            try:
                start = datetime.fromisoformat(e["start"].replace("Z", "+00:00")).replace(tzinfo=None)
                day = start.strftime("%A")
                if day != current_day:
                    print(f"\n{day}:")
                    current_day = day
                time_str = start.strftime("%H:%M") if not e["is_all_day"] else "All day"
                print(f"  {time_str}: {e['title']}")
            except (ValueError, TypeError):
                pass
    else:
        summary = get_schedule_summary()
        print(format_schedule_for_display(summary))
