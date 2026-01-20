"""
Metrics Extractor - Extract structured data from daily logs.

Parses inline fields (Dataview format) and normalizes data into structured JSON.
Designed to fail gracefully without breaking the main daily planner flow.

Inline field format: FieldName:: value
"""

import os
import re
import json
from datetime import datetime, timedelta
from typing import Optional
import frontmatter
from llm_client import estimate_macros


# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
METRICS_FILE = os.path.join(PROJECT_ROOT, "data", "daily_metrics.json")
LOGS_DIR = os.path.join(PROJECT_ROOT, "content", "logs")
HABITS_CONFIG = os.path.join(PROJECT_ROOT, "content", "config", "habits.md")


def parse_inline_field(content: str, field_name: str) -> Optional[str]:
    """
    Extract value from an inline field.

    Format: FieldName:: value

    Args:
        content: Full markdown content
        field_name: Name of the field (case-insensitive)

    Returns:
        str: Field value, or None if not found
    """
    pattern = rf'{re.escape(field_name)}::\s*(.+?)(?:\n|$)'
    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        return value if value else None
    return None


def normalize_sleep_hours(value: str) -> Optional[float]:
    """
    Convert various sleep formats to decimal hours.

    "6:35" -> 6.58 (6 hours 35 minutes)
    "6.35" -> 6.35 (already decimal)
    "0" or "" -> None (not filled)
    """
    if not value or str(value).strip() in ("0", ""):
        return None

    value = str(value).strip()

    if ":" in value:
        try:
            parts = value.split(":")
            hours = int(parts[0])
            minutes = int(parts[1])
            return round(hours + minutes / 60, 2)
        except (ValueError, IndexError):
            return None

    try:
        result = float(value)
        return result if result > 0 else None
    except ValueError:
        return None


def normalize_quality_score(value: str, scale_max: int = 10) -> Optional[float]:
    """
    Normalize quality scores to 1-10 scale.

    "7.6" -> 7.6
    "80" -> 8.0 (percentage converted - if > 10, divide by 10)
    "0" or "" -> None
    """
    if not value or str(value).strip() in ("0", ""):
        return None

    try:
        result = float(str(value).strip())
        if result <= 0:
            return None
        if result > scale_max:
            result = result / 10
        return round(result, 1)
    except ValueError:
        return None


def parse_training_value(value: str) -> tuple[Optional[float], Optional[int]]:
    """
    Parse training distance/time value from inline field.

    "750m/33:39" -> (750.0, 33.65)  # distance, duration in minutes
    "4.5/45" -> (4.5, 45)
    "0" or empty -> (None, None)

    Returns:
        tuple of (distance, duration_minutes)
    """
    if not value or str(value).strip() in ("0", "N/A", ""):
        return None, None

    value = str(value).strip()

    if "/" in value:
        parts = value.split("/")
        try:
            distance_str = re.sub(r'[^\d.]', '', parts[0])
            distance = float(distance_str) if distance_str else None
        except ValueError:
            distance = None

        duration_str = parts[1] if len(parts) > 1 else ""
        duration = None
        if duration_str:
            if ":" in duration_str:
                try:
                    first, second = duration_str.split(":")
                    first_val = int(first)
                    second_val = int(second)

                    if first_val >= 10:
                        duration = first_val + round(second_val / 60, 2)
                    else:
                        duration = first_val * 60 + second_val
                except ValueError:
                    pass
            else:
                try:
                    duration = int(float(duration_str))
                except ValueError:
                    pass

        return distance, duration

    try:
        return float(value), None
    except ValueError:
        return None, None


def parse_quick_log(content: str) -> dict:
    """
    Parse the Quick Log inline fields.

    Returns:
        dict with sleep, weight, mood data
    """
    result = {
        "sleep": {"hours": None, "quality": None},
        "weight_lbs": None,
        "mood": {"morning": None, "bedtime": None}
    }

    weight_val = parse_inline_field(content, "Weight")
    if weight_val:
        try:
            w = float(weight_val)
            result["weight_lbs"] = w if w > 0 else None
        except ValueError:
            pass

    sleep_val = parse_inline_field(content, "Sleep")
    result["sleep"]["hours"] = normalize_sleep_hours(sleep_val)

    sleep_quality_val = parse_inline_field(content, "Sleep_Quality")
    result["sleep"]["quality"] = normalize_quality_score(sleep_quality_val)

    mood_am_val = parse_inline_field(content, "Mood_AM")
    result["mood"]["morning"] = normalize_quality_score(mood_am_val)

    mood_pm_val = parse_inline_field(content, "Mood_PM")
    result["mood"]["bedtime"] = normalize_quality_score(mood_pm_val)

    return result


def parse_training_output(content: str, workout_type: str = "") -> dict:
    """
    Parse Training Output inline fields.

    Returns:
        dict with workout_type and activities list
    """
    result = {
        "workout_type": workout_type,
        "activities": [],
        "strength_exercises": []
    }

    activity_types = [
        ("Swim", "swim", "m"),
        ("Bike", "bike", "mi"),
        ("Run", "run", "mi")
    ]

    avg_hr_val = parse_inline_field(content, "Avg_HR")
    avg_hr = None
    if avg_hr_val:
        try:
            avg_hr = int(float(avg_hr_val))
        except ValueError:
            pass

    for field_name, activity_type, distance_unit in activity_types:
        field_val = parse_inline_field(content, field_name)
        if field_val:
            distance, duration = parse_training_value(field_val)
            if distance or duration:
                result["activities"].append({
                    "type": activity_type,
                    "distance": distance,
                    "distance_unit": distance_unit,
                    "duration_minutes": duration,
                    "avg_hr": avg_hr,
                    "avg_watts": None
                })

    return result


def parse_strength_log(content: str) -> list:
    """
    Parse Strength Log inline fields.

    Format: Exercise_Name:: 3x10 @ 135

    Returns:
        list of exercise dicts
    """
    exercises = []

    # Find Strength Log section
    match = re.search(r"##\s*Strength Log.*?\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not match:
        return exercises

    section = match.group(1)

    # Parse inline fields with format: Name:: sets x reps @ weight
    pattern = r'(\w[\w\s_]+)::\s*(\d+)\s*x\s*(\d+)\s*@\s*(\d+(?:\.\d+)?)'

    for line in section.split('\n'):
        line_match = re.search(pattern, line)
        if line_match:
            exercise = line_match.group(1).strip().replace('_', ' ')
            sets = int(line_match.group(2))
            reps = int(line_match.group(3))
            weight = float(line_match.group(4))

            # Skip placeholder values
            if exercise.lower() in ("primary_lift", "primary lift", "accessory_1", "accessory_2"):
                if sets == 0 and reps == 0 and weight == 0:
                    continue

            exercises.append({
                "exercise": exercise,
                "sets": sets,
                "reps": reps,
                "weight_lbs": weight
            })

    return exercises


def calculate_todo_completion(content: str) -> dict:
    """
    Count completed vs incomplete todos.

    Returns:
        dict with total, completed, completion_rate
    """
    completed = len(re.findall(r"- \[x\]", content, re.IGNORECASE))
    incomplete = len(re.findall(r"- \[ \]", content))
    total = completed + incomplete

    return {
        "total": total,
        "completed": completed,
        "completion_rate": round(completed / total, 2) if total > 0 else 0
    }


def load_habits_config() -> list:
    """
    Load habit definitions from the habits config file.

    Returns:
        list: List of habit dicts with id and name
    """
    if not os.path.exists(HABITS_CONFIG):
        return []

    try:
        post = frontmatter.load(HABITS_CONFIG)
        return post.metadata.get('habits', [])
    except Exception:
        return []


def parse_habits_section(content: str, habit_config: list) -> dict:
    """
    Parse the Daily Habits markdown section.

    Args:
        content: Full markdown content of the log
        habit_config: List of habit dicts from config

    Returns:
        dict with completed, missed, completion_rate, details
    """
    result = {
        "completed": [],
        "missed": [],
        "completion_rate": 0,
        "details": {}
    }

    if not habit_config:
        return result

    name_to_id = {h['name'].lower(): h['id'] for h in habit_config}

    match = re.search(r"##\s*Daily Habits.*?\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not match:
        return result

    section = match.group(1)

    for line in section.split("\n"):
        line = line.strip()

        checked_match = re.match(r"- \[[xX]\]\s+(.+)", line)
        if checked_match:
            habit_name = checked_match.group(1).strip().lower()
            habit_id = name_to_id.get(habit_name)
            if habit_id:
                result["completed"].append(habit_id)
                result["details"][habit_id] = True
            continue

        unchecked_match = re.match(r"- \[ \]\s+(.+)", line)
        if unchecked_match:
            habit_name = unchecked_match.group(1).strip().lower()
            habit_id = name_to_id.get(habit_name)
            if habit_id:
                result["missed"].append(habit_id)
                result["details"][habit_id] = False

    total = len(result["completed"]) + len(result["missed"])
    if total > 0:
        result["completion_rate"] = round(len(result["completed"]) / total, 2)

    return result


def calculate_habit_streaks(entries: list, habit_config: list) -> dict:
    """
    Calculate current and longest streaks for each habit.

    Args:
        entries: List of daily_metrics entries (sorted by date ascending)
        habit_config: List of habit dicts from config

    Returns:
        dict: {habit_id: {"current": int, "longest": int}}
    """
    streaks = {}

    if not habit_config:
        return streaks

    sorted_entries = sorted(entries, key=lambda x: x["date"], reverse=True)

    for habit in habit_config:
        habit_id = habit["id"]
        current_streak = 0
        longest_streak = 0
        temp_streak = 0
        counting_current = True

        for entry in sorted_entries:
            habits_data = entry.get("habits", {})
            details = habits_data.get("details", {})

            if details.get(habit_id, False):
                temp_streak += 1
                if counting_current:
                    current_streak = temp_streak
            else:
                longest_streak = max(longest_streak, temp_streak)
                temp_streak = 0
                counting_current = False

        longest_streak = max(longest_streak, temp_streak)

        streaks[habit_id] = {
            "current": current_streak,
            "longest": longest_streak
        }

    return streaks


def calculate_weekly_summaries(entries: list, habit_config: list) -> dict:
    """
    Aggregate habit data by ISO week.

    Returns:
        dict: {"2025-W52": {"meditation": 0.71, ...}, ...}
    """
    summaries = {}

    if not habit_config or not entries:
        return summaries

    weeks = {}
    for entry in entries:
        date_obj = datetime.strptime(entry["date"], "%Y-%m-%d")
        year, week_num, _ = date_obj.isocalendar()
        week_key = f"{year}-W{week_num:02d}"

        if week_key not in weeks:
            weeks[week_key] = []
        weeks[week_key].append(entry)

    habit_ids = [h["id"] for h in habit_config]

    for week_key, week_entries in weeks.items():
        week_summary = {}

        for habit_id in habit_ids:
            completed_count = 0
            total_count = 0

            for entry in week_entries:
                habits_data = entry.get("habits", {})
                details = habits_data.get("details", {})

                if habit_id in details:
                    total_count += 1
                    if details[habit_id]:
                        completed_count += 1

            if total_count > 0:
                week_summary[habit_id] = round(completed_count / total_count, 2)
            else:
                week_summary[habit_id] = None

        total_habits = 0
        completed_habits = 0
        for entry in week_entries:
            habits_data = entry.get("habits", {})
            completed_habits += len(habits_data.get("completed", []))
            total_habits += len(habits_data.get("completed", [])) + len(habits_data.get("missed", []))

        week_summary["_overall"] = round(completed_habits / total_habits, 2) if total_habits > 0 else None

        summaries[week_key] = week_summary

    return summaries


def calculate_habit_trends(weekly_summaries: dict, habit_config: list) -> dict:
    """
    Determine if each habit is improving, stable, or declining.

    Returns:
        dict: {habit_id: "improving" | "stable" | "declining" | "insufficient_data"}
    """
    trends = {}

    if not habit_config or not weekly_summaries:
        return trends

    sorted_weeks = sorted(weekly_summaries.keys())

    if len(sorted_weeks) < 2:
        for habit in habit_config:
            trends[habit["id"]] = "insufficient_data"
        return trends

    current_week = weekly_summaries[sorted_weeks[-1]]
    previous_week = weekly_summaries[sorted_weeks[-2]]

    for habit in habit_config:
        habit_id = habit["id"]
        current_rate = current_week.get(habit_id)
        previous_rate = previous_week.get(habit_id)

        if current_rate is None or previous_rate is None:
            trends[habit_id] = "insufficient_data"
        elif current_rate > previous_rate + 0.1:
            trends[habit_id] = "improving"
        elif current_rate < previous_rate - 0.1:
            trends[habit_id] = "declining"
        else:
            trends[habit_id] = "stable"

    return trends


def extract_workout_type_from_title(content: str) -> str:
    """
    Extract workout type from the daily log title.

    Title format: "2025-12-14: [Run Day]"
    """
    match = re.search(r"title:.*?\[(\w+)\s*Day\]", content, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return ""


def extract_fuel_log(content: str) -> Optional[str]:
    """
    Extract the Fuel Log section from daily log content.

    Returns:
        str: Fuel log text, or None if not found or empty
    """
    if "## Fuel Log" not in content:
        return None

    fuel_start = content.index("## Fuel Log") + len("## Fuel Log")
    remaining = content[fuel_start:]

    next_section = remaining.find("\n## ")
    fuel_text = remaining[:next_section].strip() if next_section != -1 else remaining.strip()

    # Remove inline fields (calories_so_far, protein_so_far)
    fuel_text = re.sub(r'^(calories_so_far|protein_so_far)::\s*\d*\s*$', '', fuel_text, flags=re.MULTILINE)
    fuel_text = fuel_text.strip()

    # Remove comments
    fuel_text = re.sub(r'<!--.*?-->', '', fuel_text, flags=re.DOTALL).strip()

    if len(fuel_text) < 10:
        return None

    return fuel_text


def extract_daily_metrics(date_str: str) -> Optional[dict]:
    """
    Extract all metrics from a single day's log file.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        dict: Standardized metrics for the day, or None if file not found
    """
    log_path = os.path.join(LOGS_DIR, f"{date_str}.md")

    if not os.path.exists(log_path):
        return None

    notes = []

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None

    result = {
        "date": date_str,
        "extracted_at": datetime.now().isoformat()
    }

    workout_type = extract_workout_type_from_title(content)

    # Parse quick log (sleep, weight, mood)
    try:
        stats = parse_quick_log(content)
        result["sleep"] = stats["sleep"]
        result["weight_lbs"] = stats["weight_lbs"]
        result["mood"] = stats["mood"]
    except Exception as e:
        notes.append(f"Stats parsing failed: {e}")
        result["sleep"] = {"hours": None, "quality": None}
        result["weight_lbs"] = None
        result["mood"] = {"morning": None, "bedtime": None}

    # Parse training output
    try:
        training = parse_training_output(content, workout_type)
        strength = parse_strength_log(content)
        training["strength_exercises"] = strength
        result["training"] = training
    except Exception as e:
        notes.append(f"Training parsing failed: {e}")
        result["training"] = {"workout_type": workout_type, "activities": [], "strength_exercises": []}

    # Parse todo completion
    try:
        result["todos"] = calculate_todo_completion(content)
    except Exception as e:
        notes.append(f"Todo parsing failed: {e}")
        result["todos"] = {"total": 0, "completed": 0, "completion_rate": 0}

    # Parse habits
    try:
        habit_config = load_habits_config()
        if habit_config:
            result["habits"] = parse_habits_section(content, habit_config)
        else:
            result["habits"] = {"completed": [], "missed": [], "completion_rate": 0, "details": {}}
    except Exception as e:
        notes.append(f"Habit parsing failed: {e}")
        result["habits"] = {"completed": [], "missed": [], "completion_rate": 0, "details": {}}

    # Extract and estimate nutrition from Fuel Log
    try:
        fuel_log = extract_fuel_log(content)
        if fuel_log:
            macros = estimate_macros(fuel_log)
            if macros:
                result["nutrition"] = macros
            else:
                result["nutrition"] = {
                    "calories": None,
                    "protein_g": None,
                    "carbs_g": None,
                    "fat_g": None,
                    "fiber_g": None,
                    "line_items": []
                }
                notes.append("Fuel log found but macro estimation failed")
        else:
            result["nutrition"] = {
                "calories": None,
                "protein_g": None,
                "carbs_g": None,
                "fat_g": None,
                "fiber_g": None,
                "line_items": []
            }
            notes.append("No fuel log found")
    except Exception as e:
        notes.append(f"Nutrition parsing failed: {e}")
        result["nutrition"] = {
            "calories": None,
            "protein_g": None,
            "carbs_g": None,
            "fat_g": None,
            "fiber_g": None,
            "line_items": []
        }

    result["extraction_notes"] = notes

    return result


def append_to_metrics_file(entry: dict) -> bool:
    """
    Append a daily entry to the metrics JSON file.

    Creates file/directory if they don't exist.
    Avoids duplicate entries for the same date.

    Returns:
        bool: True if successfully saved, False otherwise
    """
    try:
        data_dir = os.path.dirname(METRICS_FILE)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        if os.path.exists(METRICS_FILE):
            try:
                with open(METRICS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                backup_path = METRICS_FILE + ".backup"
                os.rename(METRICS_FILE, backup_path)
                data = {"version": "1.0", "entries": []}
        else:
            data = {"version": "1.0", "entries": []}

        existing_dates = {e["date"] for e in data.get("entries", [])}
        if entry["date"] in existing_dates:
            return True

        data["entries"].append(entry)
        data["last_updated"] = datetime.now().isoformat()

        habit_config = load_habits_config()
        if habit_config:
            data["streaks"] = calculate_habit_streaks(data["entries"], habit_config)
            data["weekly_summaries"] = calculate_weekly_summaries(data["entries"], habit_config)
            data["trends"] = calculate_habit_trends(data["weekly_summaries"], habit_config)

        temp_path = METRICS_FILE + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        if os.path.exists(METRICS_FILE):
            os.remove(METRICS_FILE)
        os.rename(temp_path, METRICS_FILE)

        return True

    except Exception as e:
        print(f"   Error saving metrics: {e}")
        return False


def extract_and_save_yesterday() -> Optional[dict]:
    """
    Main entry point: Extract yesterday's metrics and save to file.

    Called from daily_planner.py at the start of creating today's log.

    Returns:
        dict: Extracted metrics, or None if extraction failed
    """
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")

    metrics = extract_daily_metrics(date_str)

    if metrics is None:
        return None

    if append_to_metrics_file(metrics):
        return metrics

    return None


if __name__ == "__main__":
    print("Testing metrics extraction...")
    result = extract_and_save_yesterday()
    if result:
        print(f"Extracted metrics for {result['date']}:")
        print(json.dumps(result, indent=2))
    else:
        print("No metrics extracted")
