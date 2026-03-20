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
import re
import frontmatter
from datetime import datetime, timedelta

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from llm_client import generate_weekly_protocol

# CONFIGURATION
RYAN_CONFIG = "content/config/ryan.md"
PROTOCOL_DIR = "content/config"
LOGS_DIR = "content/logs"
METRICS_FILE = "data/daily_metrics.json"


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


def _parse_inline_field(content: str, field_name: str):
    """Parse inline field values (Field:: value) from log markdown."""
    match = re.search(
        rf'(?m)^[ \t]*{re.escape(field_name)}::[ \t]*([^\n\r]*)[ \t]*$',
        content
    )
    if not match:
        return None
    value = match.group(1).strip()
    return value if value else None


def _safe_float(value):
    """Parse a value to float if possible, otherwise return None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    if ":" in text:
        try:
            hours_str, minutes_str = text.split(":", 1)
            hours = int(hours_str)
            minutes = int(minutes_str)
            return round(hours + minutes / 60, 2)
        except (ValueError, TypeError):
            pass

    text = text.replace(",", "")
    number = re.search(r'-?\d+(?:\.\d+)?', text)
    if not number:
        return None
    try:
        return float(number.group(0))
    except ValueError:
        return None


def _extract_todo_completion_rate(content: str) -> float:
    """Extract checkbox completion rate from Today's Todos section."""
    if "## Today's Todos" not in content:
        return 0.0

    todos_section = content.split("## Today's Todos", 1)[1]
    next_section_idx = todos_section.find("\n## ")
    if next_section_idx != -1:
        todos_section = todos_section[:next_section_idx]

    completed = 0
    total = 0
    for raw in todos_section.splitlines():
        line = raw.strip()
        if line.startswith("- [x]"):
            completed += 1
            total += 1
        elif line.startswith("- [ ]"):
            total += 1

    if total == 0:
        return 0.0
    return round(completed / total, 2)


def _load_metrics_index() -> dict:
    """Load daily metrics from V2 SQLite, indexed by date."""
    try:
        project_root = os.path.join(os.path.dirname(__file__), '..')
        sys.path.insert(0, os.path.join(project_root, "telegram-bot"))
        from v2.infra.sqlite_state_store import SQLiteStateStore

        store = SQLiteStateStore()
        chat_id = int(os.environ.get("OWNER_CHAT_ID", "0"))
        if not chat_id:
            return {}

        entries = store.get_all_metrics_entries(chat_id)
        return {e["date"]: e for e in entries if e.get("date")}
    except Exception:
        return {}


def _calculate_last_week_range(year, week):
    """Calculate the Monday and date range for last week."""
    last_week = week - 1
    last_year = year
    if last_week < 1:
        last_year = year - 1
        dec_31 = datetime(last_year, 12, 31)
        last_week = dec_31.isocalendar()[1]

    jan_4 = datetime(last_year, 1, 4)
    week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
    target_monday = week_1_monday + timedelta(weeks=last_week - 1)
    return target_monday


def _read_private_day_log(date_str: str) -> str:
    """Read private day log markdown for narrative context."""
    private_dir = os.environ.get("HISTORY_DIR", os.path.expanduser("~/.bestupid-private"))
    private_logs_dir = os.path.join(private_dir, "day_logs")

    for dir_path in [LOGS_DIR, private_logs_dir]:
        path = os.path.join(dir_path, f"{date_str}.md")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except OSError:
                pass
    return ""


def _read_logs_from_v2(year, week) -> list:
    """Read last week's data from V2 SQLite."""
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'telegram-bot'))
    from v2.infra.sqlite_state_store import SQLiteStateStore

    store = SQLiteStateStore()
    chat_id = int(os.environ.get("OWNER_CHAT_ID", "0"))
    if not chat_id:
        raise ValueError("OWNER_CHAT_ID not set")

    target_monday = _calculate_last_week_range(year, week)

    logs = []
    for day_offset in range(7):
        log_date = target_monday + timedelta(days=day_offset)
        date_str = log_date.strftime("%Y-%m-%d")

        snapshot = store.get_day_snapshot(chat_id, date_str)
        if not snapshot:
            continue

        metrics = snapshot.metrics or {}
        sleep_hours = _safe_float(metrics.get("Sleep")) or 0
        weight = _safe_float(metrics.get("Weight")) or 0

        habits = snapshot.habits or []
        done_count = sum(1 for h in habits if h["status"] == "done")
        total = len(habits)
        compliance = round((done_count / total * 100) if total else 0, 1)

        narrative = _read_private_day_log(date_str)

        logs.append({
            "date": date_str,
            "content": narrative,
            "stats": {
                "compliance": compliance,
                "sleep_hours": sleep_hours,
                "weight": weight,
            },
            "narrative": narrative,
        })
    return logs


def read_last_week_logs(year, week):
    """Read all daily logs from last week. Tries V2 SQLite first, falls back to markdown."""
    try:
        logs = _read_logs_from_v2(year, week)
        if logs:
            print(f"   Read {len(logs)} days from V2 SQLite")
            return logs
    except Exception as e:
        print(f"   V2 read failed ({e}), falling back to markdown logs")

    # Legacy fallback: read from markdown files
    logs = []
    metrics_index = _load_metrics_index()
    target_monday = _calculate_last_week_range(year, week)

    for day_offset in range(7):
        log_date = target_monday + timedelta(days=day_offset)
        log_date_str = log_date.strftime("%Y-%m-%d")
        log_path = os.path.join(LOGS_DIR, f"{log_date_str}.md")

        if os.path.exists(log_path):
            try:
                post = frontmatter.load(log_path)
                content = post.content
                metrics_entry = metrics_index.get(log_date_str, {})

                completion_rate = metrics_entry.get("todos", {}).get("completion_rate")
                if completion_rate is None:
                    completion_rate = _extract_todo_completion_rate(content)
                compliance_pct = round(completion_rate * 100, 1)

                sleep_hours = metrics_entry.get("sleep", {}).get("hours")
                if sleep_hours is None:
                    sleep_hours = _safe_float(_parse_inline_field(content, "Sleep"))
                sleep_hours = sleep_hours or 0

                weight_lbs = metrics_entry.get("weight_lbs")
                if weight_lbs is None:
                    weight_lbs = _safe_float(_parse_inline_field(content, "Weight"))
                weight_lbs = weight_lbs or 0

                log_data = {
                    "date": log_date_str,
                    "content": content,
                    "stats": {
                        "compliance": compliance_pct,
                        "sleep_hours": sleep_hours,
                        "weight": weight_lbs,
                    },
                    "narrative": content,
                }
                logs.append(log_data)
            except Exception as e:
                print(f"Warning: Could not read {log_path}: {e}")

    return logs

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

    # Auto-finalize DRAFTs older than 2 weeks
    from pathlib import Path as _Path
    for draft in sorted(_Path(PROTOCOL_DIR).glob("protocol_*_DRAFT.md")):
        date_match = re.search(r'protocol_(\d{4}-\d{2}-\d{2})_DRAFT', draft.name)
        if date_match:
            draft_monday = datetime.strptime(date_match.group(1), "%Y-%m-%d")
            if (datetime.now() - draft_monday).days >= 14:
                final = draft.with_name(draft.name.replace("_DRAFT.md", ".md"))
                draft.rename(final)
                print(f"Auto-finalized old draft: {draft.name}")

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
