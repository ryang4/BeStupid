"""
Weekly Protocol Planner - AI-Generated Training Plans

Generates next week's training protocol using Ollama (qwen).
Reads: ryan.md + last week's protocol + last week's logs
Outputs: protocol_YYYY-WXX_DRAFT.md for human review

Usage:
    python weekly_planner.py                    # Generate next week
    python weekly_planner.py --this-week        # Generate for current week
    python weekly_planner.py --week 50          # Generate specific week
    python weekly_planner.py --date 2025-12-29  # Generate for specific Monday
    python weekly_planner.py --finalize         # Remove _DRAFT suffix
"""

import os
import sys
import json
import argparse
import frontmatter
from datetime import datetime, timedelta

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from llm_client import generate_weekly_protocol

# CONFIGURATION
RYAN_CONFIG = "content/config/ryan.md"
PROTOCOL_DIR = "content/config"
LOGS_DIR = "content/logs"


def get_next_week():
    """
    Calculate next week's Monday date.

    Returns:
        tuple: (year, week_number, monday_date_str)
    """
    today = datetime.now()
    # Find next Monday
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7  # If today is Monday, get next Monday
    next_monday = today + timedelta(days=days_until_monday)
    year, week, _ = next_monday.isocalendar()
    monday_str = next_monday.strftime("%Y-%m-%d")
    return year, week, monday_str


def get_this_week():
    """
    Calculate the current week's Monday date.

    Returns:
        tuple: (year, week_number, monday_date_str)
    """
    today = datetime.now()
    # Find most recent Monday (including today if Monday)
    days_since_monday = today.weekday()  # Monday=0, Sunday=6
    this_monday = today - timedelta(days=days_since_monday)
    year, week, _ = this_monday.isocalendar()
    monday_str = this_monday.strftime("%Y-%m-%d")
    return year, week, monday_str


def read_last_protocol(target_monday_str):
    """
    Read last week's protocol file.

    Args:
        target_monday_str: Monday date of target week (YYYY-MM-DD)

    Returns:
        str or None: Protocol content if found
    """
    # Calculate last week's Monday
    target_monday = datetime.strptime(target_monday_str, "%Y-%m-%d")
    last_monday = target_monday - timedelta(days=7)
    last_monday_str = last_monday.strftime("%Y-%m-%d")

    # Try new date-based format first
    protocol_file = f"protocol_{last_monday_str}.md"
    protocol_path = os.path.join(PROTOCOL_DIR, protocol_file)

    if os.path.exists(protocol_path):
        with open(protocol_path, 'r', encoding='utf-8') as f:
            return f.read()

    # Fallback to old week-number format during transition
    year, week, _ = last_monday.isocalendar()
    old_protocol_file = f"protocol_{year}-W{week:02d}.md"
    old_protocol_path = os.path.join(PROTOCOL_DIR, old_protocol_file)

    if os.path.exists(old_protocol_path):
        print(f"Note: Using legacy protocol format {old_protocol_file}")
        with open(old_protocol_path, 'r', encoding='utf-8') as f:
            return f.read()

    return None


def read_last_week_logs(year, week):
    """Read all daily logs from last week."""
    logs = []

    # Calculate last week's date range
    last_week = week - 1
    last_year = year
    if last_week < 1:
        last_year = year - 1
        dec_31 = datetime(last_year, 12, 31)
        last_week = dec_31.isocalendar()[1]

    # Get Monday of last week
    # ISO week 1 starts on the first Monday of the year
    jan_4 = datetime(last_year, 1, 4)  # Week 1 always contains Jan 4
    week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
    target_monday = week_1_monday + timedelta(weeks=last_week - 1)

    # Read 7 days of logs
    for day_offset in range(7):
        log_date = target_monday + timedelta(days=day_offset)
        log_date_str = log_date.strftime("%Y-%m-%d")
        # Flat file path (not page bundle)
        log_path = os.path.join(LOGS_DIR, f"{log_date_str}.md")

        if os.path.exists(log_path):
            try:
                post = frontmatter.load(log_path)

                log_data = {
                    "date": log_date_str,
                    "content": post.content,
                    "stats": {
                        "compliance": post.get('Compliance', 0),
                        "sleep_hours": post.get('Sleep Hours', 0),
                        "weight": post.get('Weight (lbs)', 0),
                    },
                    "narrative": post.content  # Full text for AI analysis
                }
                logs.append(log_data)
            except Exception as e:
                print(f"⚠️  Warning: Could not read {log_path}: {e}")

    return logs


# CONFIGURATION
METRICS_FILE = "data/daily_metrics.json"


def get_strength_exercise_history(weeks_back=4):
    """
    Aggregate strength exercise data from daily_metrics.json.

    Args:
        weeks_back: Number of weeks of history to include

    Returns:
        dict: {
            "exercises": {
                "close grip bench press": [
                    {"date": "2026-01-06", "sets": 3, "reps": 8, "weight": 115, "volume": 2760},
                    ...
                ],
                ...
            },
            "summary": {
                "close grip bench press": {
                    "sessions": 4,
                    "max_weight": 115,
                    "avg_reps": 7.5,
                    "trend": "stable",
                    "last_workout": {"date": "2026-01-06", "sets": 3, "reps": 8, "weight": 115}
                },
                ...
            }
        }
    """
    metrics_path = os.path.join(os.path.dirname(__file__), '..', METRICS_FILE)

    if not os.path.exists(metrics_path):
        return {"exercises": {}, "summary": {}}

    with open(metrics_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cutoff_date = (datetime.now() - timedelta(weeks=weeks_back)).strftime("%Y-%m-%d")

    exercises = {}
    for entry in data.get("entries", []):
        if entry.get("date", "") < cutoff_date:
            continue

        for ex in entry.get("training", {}).get("strength_exercises", []):
            name = ex.get("exercise", "").lower().strip()
            if not name:
                continue

            if name not in exercises:
                exercises[name] = []

            sets = ex.get("sets", 0) or 0
            reps = ex.get("reps", 0) or 0
            weight = ex.get("weight_lbs", 0) or 0

            exercises[name].append({
                "date": entry["date"],
                "sets": sets,
                "reps": reps,
                "weight": weight,
                "volume": sets * reps * weight
            })

    # Sort each exercise's history by date (most recent first)
    for name in exercises:
        exercises[name].sort(key=lambda x: x["date"], reverse=True)

    # Generate summaries
    summary = {}
    for name, history in exercises.items():
        if not history:
            continue

        summary[name] = {
            "sessions": len(history),
            "max_weight": max(h["weight"] for h in history),
            "avg_reps": sum(h["reps"] for h in history) / len(history),
            "last_workout": history[0],
            "trend": calculate_exercise_trend(history)
        }

    return {"exercises": exercises, "summary": summary}


def calculate_exercise_trend(history):
    """
    Determine if exercise performance is improving, stable, or declining.

    Compares average volume of last 2 sessions vs previous 2 sessions.

    Args:
        history: List of workout dicts sorted by date (most recent first)

    Returns:
        str: "improving", "stable", "declining", or "insufficient_data"
    """
    if len(history) < 2:
        return "insufficient_data"

    # Compare last 2 sessions vs previous 2
    recent = history[:2]
    previous = history[2:4] if len(history) >= 4 else history[2:]

    if not previous:
        return "stable"

    recent_avg_volume = sum(h["volume"] for h in recent) / len(recent)
    previous_avg_volume = sum(h["volume"] for h in previous) / len(previous)

    if previous_avg_volume == 0:
        return "stable"

    change = (recent_avg_volume - previous_avg_volume) / previous_avg_volume

    if change > 0.05:
        return "improving"
    elif change < -0.05:
        return "declining"
    return "stable"


def format_exercise_history_for_prompt(exercise_history):
    """
    Format exercise history into a readable string for the LLM prompt.

    Args:
        exercise_history: Dict from get_strength_exercise_history()

    Returns:
        str: Formatted markdown text for LLM consumption
    """
    if not exercise_history or not exercise_history.get("summary"):
        return "No strength exercise history available."

    lines = []
    for exercise, data in sorted(exercise_history["summary"].items()):
        last = data["last_workout"]
        lines.append(f"### {exercise.title()}")
        lines.append(f"- **Trend:** {data['trend'].replace('_', ' ').title()}")
        lines.append(f"- **Sessions tracked:** {data['sessions']}")
        lines.append(f"- **Last session:** {last['date']} - {last['sets']}x{last['reps']} @ {last['weight']} lbs")
        lines.append(f"- **Max weight achieved:** {data['max_weight']} lbs")

        # Add progression recommendation
        if data['trend'] == 'improving':
            lines.append("- **Recommendation:** Increase weight by 5 lbs or add 1-2 reps")
        elif data['trend'] == 'declining':
            lines.append("- **Recommendation:** Hold weight, focus on form and hitting all reps")
        else:
            lines.append("- **Recommendation:** Try adding 1 rep per set or 2.5-5 lbs")

        lines.append("")  # Blank line between exercises

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate weekly training protocol")
    parser.add_argument('--week', type=int, help='Specific week number to generate')
    parser.add_argument('--date', type=str, help='Specific Monday date (YYYY-MM-DD) to generate')
    parser.add_argument('--this-week', action='store_true', dest='this_week',
                       help='Generate for current week (most recent Monday)')
    parser.add_argument('--finalize', action='store_true', help='Remove _DRAFT suffix from latest protocol')
    args = parser.parse_args()

    # Handle finalize mode
    if args.finalize:
        # Find most recent DRAFT file
        draft_files = [f for f in os.listdir(PROTOCOL_DIR) if f.endswith('_DRAFT.md')]
        if not draft_files:
            print("No DRAFT protocol files found")
            sys.exit(1)

        latest_draft = sorted(draft_files)[-1]
        draft_path = os.path.join(PROTOCOL_DIR, latest_draft)
        final_path = draft_path.replace('_DRAFT.md', '.md')

        os.rename(draft_path, final_path)
        print(f"Finalized: {latest_draft} -> {os.path.basename(final_path)}")
        sys.exit(0)

    # Determine target week
    if args.date:
        monday_str = args.date
        target_monday = datetime.strptime(monday_str, "%Y-%m-%d")
        year, week, _ = target_monday.isocalendar()
    elif args.week:
        year = datetime.now().year
        week = args.week
        # Calculate Monday for that week
        jan_4 = datetime(year, 1, 4)
        week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
        target_monday = week_1_monday + timedelta(weeks=week - 1)
        monday_str = target_monday.strftime("%Y-%m-%d")
    elif args.this_week:
        year, week, monday_str = get_this_week()
    else:
        year, week, monday_str = get_next_week()

    print(f"Generating protocol for week of {monday_str} (W{week:02d})...")

    # Read inputs
    print("Reading Ryan's goals...")
    with open(RYAN_CONFIG, 'r', encoding='utf-8') as f:
        goals = f.read()

    print("Reading last week's protocol...")
    last_protocol = read_last_protocol(monday_str)
    if last_protocol:
        print("   Found previous protocol")
    else:
        print("   No previous protocol (first week)")

    print("Reading last week's logs...")
    last_week_logs = read_last_week_logs(year, week)
    print(f"   Found {len(last_week_logs)} daily logs")

    print("Gathering exercise history...")
    exercise_history = get_strength_exercise_history(weeks_back=4)
    exercise_count = len(exercise_history.get('summary', {}))
    print(f"   Found {exercise_count} unique exercises tracked")

    # Generate protocol using AI
    print("Generating weekly protocol...")
    print("   (This may take 30-60 seconds...)")

    try:
        protocol_content = generate_weekly_protocol(
            goals,
            last_protocol,
            last_week_logs,
            exercise_history=exercise_history
        )
    except RuntimeError as e:
        # This catches when all LLM backends fail
        print(f"\n{e}")
        print("\nTo fix: Set HF_TOKEN in .env file or run 'ollama serve' in another terminal")
        sys.exit(1)
    except Exception as e:
        print(f"\nError generating protocol: {e}")
        sys.exit(1)

    # Save as DRAFT with date-based naming
    output_filename = f"protocol_{monday_str}_DRAFT.md"
    output_path = os.path.join(PROTOCOL_DIR, output_filename)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(protocol_content)

    print(f"\nProtocol generated: {output_filename}")
    print("\nNext steps:")
    print(f"   1. Review/edit in Obsidian: {output_path}")
    print("   2. When ready, finalize: python weekly_planner.py --finalize")
    print(f"   3. Or manually rename to: protocol_{monday_str}.md")


if __name__ == "__main__":
    main()
