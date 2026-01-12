"""
Metrics Extractor - Standardized data extraction from daily logs.

Parses markdown tables and normalizes data formats into structured JSON.
Designed to fail gracefully without breaking the main daily planner flow.
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

    # Check for HH:MM format
    if ":" in value:
        try:
            parts = value.split(":")
            hours = int(parts[0])
            minutes = int(parts[1])
            return round(hours + minutes / 60, 2)
        except (ValueError, IndexError):
            return None

    # Already decimal
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
        # If value seems to be a percentage (>10), convert to 1-10 scale
        if result > scale_max:
            result = result / 10
        return round(result, 1)
    except ValueError:
        return None


def parse_daily_stats_table(content: str) -> dict:
    """
    Parse the Daily Stats markdown table.

    Returns:
        dict with sleep, weight, mood data
    """
    result = {
        "sleep": {"hours": None, "quality": None},
        "weight_lbs": None,
        "mood": {"morning": None, "bedtime": None}
    }

    # Find Daily Stats section
    match = re.search(r"##\s*Daily Stats.*?\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not match:
        return result

    section = match.group(1)

    # Parse table rows
    for line in section.split("\n"):
        if "|" not in line or "---" in line or "Metric" in line:
            continue

        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 3:
            continue

        metric = cells[1].lower().replace("**", "").strip()
        value = cells[2].strip()

        if "sleep hours" in metric:
            result["sleep"]["hours"] = normalize_sleep_hours(value)
        elif "sleep quality" in metric:
            result["sleep"]["quality"] = normalize_quality_score(value)
        elif "weight" in metric:
            try:
                w = float(value) if value and value != "0" else None
                result["weight_lbs"] = w if w and w > 0 else None
            except ValueError:
                pass
        elif "morning mood" in metric:
            result["mood"]["morning"] = normalize_quality_score(value)
        elif "bedtime mood" in metric:
            result["mood"]["bedtime"] = normalize_quality_score(value)

    return result


def parse_training_value(value: str) -> tuple[Optional[float], Optional[int]]:
    """
    Parse training distance/time value.

    "6/1:15" -> (6.0, 75)  # distance, duration in minutes
    "4/20" -> (4.0, 20)
    "0" or "N/A" -> (None, None)

    Returns:
        tuple of (distance, duration_minutes)
    """
    if not value or str(value).strip() in ("0", "N/A", ""):
        return None, None

    value = str(value).strip()

    if "/" in value:
        parts = value.split("/")
        try:
            # Remove non-numeric characters (except decimal point) from distance
            # e.g., "750m" -> "750", "4.5mi" -> "4.5"
            distance_str = re.sub(r'[^\d.]', '', parts[0])
            distance = float(distance_str) if distance_str else None
        except ValueError:
            distance = None

        # Duration could be "20" (minutes) or "1:15" (h:mm) or "33:39" (mm:ss)
        duration_str = parts[1] if len(parts) > 1 else ""
        duration = None
        if duration_str:
            if ":" in duration_str:
                try:
                    first, second = duration_str.split(":")
                    first_val = int(first)
                    second_val = int(second)

                    # Heuristic: if first part >= 10, treat as MM:SS, else HH:MM
                    # (e.g., "33:39" = 33min 39sec, but "1:15" = 1hr 15min)
                    if first_val >= 10:
                        # MM:SS format - convert to decimal minutes
                        duration = first_val + round(second_val / 60, 2)
                    else:
                        # HH:MM format - convert to minutes
                        duration = first_val * 60 + second_val
                except ValueError:
                    pass
            else:
                try:
                    duration = int(float(duration_str))
                except ValueError:
                    pass

        return distance, duration

    # Just a number (distance only)
    try:
        return float(value), None
    except ValueError:
        return None, None


def parse_training_output_table(content: str, workout_type: str = "") -> dict:
    """
    Parse Training Output markdown table.

    Returns:
        dict with workout_type and activities list
    """
    result = {
        "workout_type": workout_type,
        "activities": [],
        "strength_exercises": []
    }

    # Find Training Output section
    match = re.search(r"##\s*Training Output.*?\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not match:
        return result

    section = match.group(1)

    # Parse table rows
    for line in section.split("\n"):
        if "|" not in line or "---" in line or "Activity" in line:
            continue

        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 4:
            continue

        activity_cell = cells[1].lower().replace("**", "").strip()
        dist_time = cells[2].strip()
        hr_watts = cells[3].strip()

        # Determine activity type and unit
        activity_type = None
        distance_unit = "mi"

        if "swim" in activity_cell:
            activity_type = "swim"
            distance_unit = "m"  # Swimming typically in meters
        elif "bike" in activity_cell:
            activity_type = "bike"
        elif "run" in activity_cell:
            activity_type = "run"

        if activity_type:
            distance, duration = parse_training_value(dist_time)

            # Parse HR/Watts
            avg_hr = None
            avg_watts = None
            if hr_watts and hr_watts not in ("0", "N/A", ""):
                try:
                    # Assume it's HR if < 300, watts if >= 300
                    val = int(float(hr_watts))
                    if val < 300:
                        avg_hr = val
                    else:
                        avg_watts = val
                except ValueError:
                    pass

            if distance or duration:  # Only add if we have some data
                result["activities"].append({
                    "type": activity_type,
                    "distance": distance,
                    "distance_unit": distance_unit,
                    "duration_minutes": duration,
                    "avg_hr": avg_hr,
                    "avg_watts": avg_watts
                })

    return result


def parse_strength_log_table(content: str) -> list:
    """
    Parse Strength Log markdown table if present.

    Returns:
        list of exercise dicts
    """
    exercises = []

    # Find Strength Log section
    match = re.search(r"##\s*Strength Log.*?\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not match:
        return exercises

    section = match.group(1)

    # Parse table rows
    for line in section.split("\n"):
        if "|" not in line or "---" in line or "Exercise" in line:
            continue

        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 5:
            continue

        exercise = cells[1].strip()

        # Skip placeholder rows
        if not exercise or exercise.lower() in ("primary lift", "accessory 1", "accessory 2"):
            try:
                # Check if values are all 0
                if all(cells[i].strip() == "0" for i in [2, 3, 4] if i < len(cells)):
                    continue
            except (IndexError, ValueError):
                continue

        try:
            sets = int(cells[2]) if cells[2].strip() and cells[2].strip() != "0" else None
            reps = int(cells[3]) if cells[3].strip() and cells[3].strip() != "0" else None
            weight = float(cells[4]) if cells[4].strip() and cells[4].strip() != "0" else None

            if sets or reps or weight:
                exercises.append({
                    "exercise": exercise,
                    "sets": sets,
                    "reps": reps,
                    "weight_lbs": weight
                })
        except (ValueError, IndexError):
            continue

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

    # Build name -> id mapping
    name_to_id = {h['name'].lower(): h['id'] for h in habit_config}

    # Find Daily Habits section
    match = re.search(r"##\s*Daily Habits.*?\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not match:
        return result

    section = match.group(1)

    # Parse checkbox lines
    for line in section.split("\n"):
        line = line.strip()

        # Match checked: - [x] or - [X]
        checked_match = re.match(r"- \[[xX]\]\s+(.+)", line)
        if checked_match:
            habit_name = checked_match.group(1).strip().lower()
            habit_id = name_to_id.get(habit_name)
            if habit_id:
                result["completed"].append(habit_id)
                result["details"][habit_id] = True
            continue

        # Match unchecked: - [ ]
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

    # Sort entries by date descending (most recent first)
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
                # Streak broken
                longest_streak = max(longest_streak, temp_streak)
                temp_streak = 0
                counting_current = False  # Stop counting current after first miss

        # Final check for longest
        longest_streak = max(longest_streak, temp_streak)

        streaks[habit_id] = {
            "current": current_streak,
            "longest": longest_streak
        }

    return streaks


def calculate_weekly_summaries(entries: list, habit_config: list) -> dict:
    """
    Aggregate habit data by ISO week.

    Args:
        entries: List of daily_metrics entries
        habit_config: List of habit dicts from config

    Returns:
        dict: {"2025-W52": {"meditation": 0.71, "reading": 0.57, ...}, ...}
    """
    summaries = {}

    if not habit_config or not entries:
        return summaries

    # Group entries by ISO week
    weeks = {}
    for entry in entries:
        date_obj = datetime.strptime(entry["date"], "%Y-%m-%d")
        year, week_num, _ = date_obj.isocalendar()
        week_key = f"{year}-W{week_num:02d}"

        if week_key not in weeks:
            weeks[week_key] = []
        weeks[week_key].append(entry)

    # Calculate per-habit completion rate for each week
    habit_ids = [h["id"] for h in habit_config]

    for week_key, week_entries in weeks.items():
        week_summary = {}

        for habit_id in habit_ids:
            completed_count = 0
            total_count = 0

            for entry in week_entries:
                habits_data = entry.get("habits", {})
                details = habits_data.get("details", {})

                # Only count if the habit was tracked that day
                if habit_id in details:
                    total_count += 1
                    if details[habit_id]:
                        completed_count += 1

            if total_count > 0:
                week_summary[habit_id] = round(completed_count / total_count, 2)
            else:
                week_summary[habit_id] = None

        # Also add overall completion rate for the week
        total_habits = 0
        completed_habits = 0
        for entry in week_entries:
            habits_data = entry.get("habits", {})
            completed_habits += len(habits_data.get("completed", []))
            completed_habits += len(habits_data.get("missed", []))
            total_habits += len(habits_data.get("completed", [])) + len(habits_data.get("missed", []))

        week_summary["_overall"] = round(completed_habits / total_habits, 2) if total_habits > 0 else None

        summaries[week_key] = week_summary

    return summaries


def calculate_habit_trends(weekly_summaries: dict, habit_config: list) -> dict:
    """
    Determine if each habit is improving, stable, or declining.

    Compares the most recent 2 weeks to determine trend direction.

    Args:
        weekly_summaries: Output from calculate_weekly_summaries()
        habit_config: List of habit dicts from config

    Returns:
        dict: {habit_id: "improving" | "stable" | "declining" | "insufficient_data"}
    """
    trends = {}

    if not habit_config or not weekly_summaries:
        return trends

    # Sort weeks chronologically (most recent last)
    sorted_weeks = sorted(weekly_summaries.keys())

    if len(sorted_weeks) < 2:
        # Not enough data for trend analysis
        for habit in habit_config:
            trends[habit["id"]] = "insufficient_data"
        return trends

    # Get last 2 weeks
    current_week = weekly_summaries[sorted_weeks[-1]]
    previous_week = weekly_summaries[sorted_weeks[-2]]

    for habit in habit_config:
        habit_id = habit["id"]
        current_rate = current_week.get(habit_id)
        previous_rate = previous_week.get(habit_id)

        if current_rate is None or previous_rate is None:
            trends[habit_id] = "insufficient_data"
        elif current_rate > previous_rate + 0.1:  # >10% improvement
            trends[habit_id] = "improving"
        elif current_rate < previous_rate - 0.1:  # >10% decline
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
    # Find Fuel Log section
    if "## Fuel Log" not in content:
        return None

    # Get text between "## Fuel Log" and next "##" or end
    fuel_start = content.index("## Fuel Log") + len("## Fuel Log")
    remaining = content[fuel_start:]

    # Find the next section header
    next_section = remaining.find("\n## ")
    if next_section != -1:
        fuel_text = remaining[:next_section].strip()
    else:
        fuel_text = remaining.strip()

    # Remove the placeholder line if it exists
    if fuel_text.startswith("*Describe your food"):
        # Remove the placeholder line and get the actual content
        lines = fuel_text.split('\n', 1)
        fuel_text = lines[1].strip() if len(lines) > 1 else ""

    # Skip if too short to analyze
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
    except Exception as e:
        return None

    result = {
        "date": date_str,
        "extracted_at": datetime.now().isoformat()
    }

    # Extract workout type from title
    workout_type = extract_workout_type_from_title(content)

    # Parse daily stats (sleep, weight, mood)
    try:
        stats = parse_daily_stats_table(content)
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
        training = parse_training_output_table(content, workout_type)
        # Also parse strength log
        strength = parse_strength_log_table(content)
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
                # estimate_macros returns: calories, protein_g, carbs_g, fat_g, fiber_g, line_items
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
        # Ensure data directory exists
        data_dir = os.path.dirname(METRICS_FILE)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # Load existing data or create new structure
        if os.path.exists(METRICS_FILE):
            try:
                with open(METRICS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                # Corrupted file - backup and start fresh
                backup_path = METRICS_FILE + ".backup"
                os.rename(METRICS_FILE, backup_path)
                data = {"version": "1.0", "entries": []}
        else:
            data = {"version": "1.0", "entries": []}

        # Check for duplicate date
        existing_dates = {e["date"] for e in data.get("entries", [])}
        if entry["date"] in existing_dates:
            return True  # Already exists, consider it a success

        # Append new entry
        data["entries"].append(entry)
        data["last_updated"] = datetime.now().isoformat()

        # Calculate and store habit analytics
        habit_config = load_habits_config()
        if habit_config:
            data["streaks"] = calculate_habit_streaks(data["entries"], habit_config)
            data["weekly_summaries"] = calculate_weekly_summaries(data["entries"], habit_config)
            data["trends"] = calculate_habit_trends(data["weekly_summaries"], habit_config)

        # Write atomically (write to temp, then rename)
        temp_path = METRICS_FILE + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        # On Windows, need to remove existing file first
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
    # Test extraction with yesterday's log
    print("Testing metrics extraction...")
    result = extract_and_save_yesterday()
    if result:
        print(f"Extracted metrics for {result['date']}:")
        print(json.dumps(result, indent=2))
    else:
        print("No metrics extracted")
