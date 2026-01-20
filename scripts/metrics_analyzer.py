"""
Metrics Analyzer - Pattern detection and trend analysis for LLM context.

Reads daily_metrics.json and computes:
- 7-day rolling averages (sleep, mood, compliance)
- Day-of-week patterns (which days have lowest compliance)
- Correlations (sleep→mood, mood→workout completion)
- Streak tracking (consecutive days of compliance/non-compliance)
- Adaptive todo recommendations based on completion rates

This module bridges the gap between raw metrics and actionable LLM prompts.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
METRICS_FILE = os.path.join(PROJECT_ROOT, "data", "daily_metrics.json")


def load_metrics() -> dict:
    """
    Load metrics from daily_metrics.json.

    Returns:
        dict: Full metrics data structure, or empty structure if file doesn't exist
    """
    if not os.path.exists(METRICS_FILE):
        return {"version": "1.0", "entries": []}

    try:
        with open(METRICS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"version": "1.0", "entries": []}


def get_entries_for_days(entries: list, n_days: int) -> list:
    """
    Get entries for the last N days (by date, not by count).

    Args:
        entries: List of metric entries
        n_days: Number of days to look back

    Returns:
        list: Filtered entries within the date range
    """
    if not entries:
        return []

    cutoff = datetime.now() - timedelta(days=n_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    return [e for e in entries if e.get("date", "") >= cutoff_str]


def compute_rolling_averages(entries: list) -> dict:
    """
    Compute 7-day rolling averages for key metrics.

    Args:
        entries: List of daily metric entries

    Returns:
        dict with rolling averages for sleep, mood, compliance, weight
    """
    recent = get_entries_for_days(entries, 7)

    if not recent:
        return {
            "sleep_hours": None,
            "sleep_quality": None,
            "mood_morning": None,
            "mood_bedtime": None,
            "todo_completion_rate": None,
            "habit_completion_rate": None,
            "weight_lbs": None,
            "days_with_data": 0
        }

    # Extract values (filter out None)
    sleep_hours = [e["sleep"]["hours"] for e in recent if e.get("sleep", {}).get("hours")]
    sleep_quality = [e["sleep"]["quality"] for e in recent if e.get("sleep", {}).get("quality")]
    mood_morning = [e["mood"]["morning"] for e in recent if e.get("mood", {}).get("morning")]
    mood_bedtime = [e["mood"]["bedtime"] for e in recent if e.get("mood", {}).get("bedtime")]
    todo_rates = [e["todos"]["completion_rate"] for e in recent if e.get("todos", {}).get("completion_rate") is not None]
    habit_rates = [e["habits"]["completion_rate"] for e in recent if e.get("habits", {}).get("completion_rate") is not None]
    weights = [e["weight_lbs"] for e in recent if e.get("weight_lbs")]

    def safe_avg(values):
        return round(sum(values) / len(values), 2) if values else None

    return {
        "sleep_hours": safe_avg(sleep_hours),
        "sleep_quality": safe_avg(sleep_quality),
        "mood_morning": safe_avg(mood_morning),
        "mood_bedtime": safe_avg(mood_bedtime),
        "todo_completion_rate": safe_avg(todo_rates),
        "habit_completion_rate": safe_avg(habit_rates),
        "weight_lbs": safe_avg(weights),
        "days_with_data": len(recent)
    }


def detect_day_of_week_patterns(entries: list) -> dict:
    """
    Analyze which days of the week have lowest compliance/completion.

    Args:
        entries: List of daily metric entries

    Returns:
        dict with weak_days list and per-day completion rates
    """
    recent = get_entries_for_days(entries, 30)  # Look at last 30 days for patterns

    if not recent:
        return {"weak_days": [], "by_day": {}}

    # Group by day of week
    day_stats = defaultdict(lambda: {"total": 0, "completed": 0, "habit_rates": []})

    for entry in recent:
        try:
            date_obj = datetime.strptime(entry["date"], "%Y-%m-%d")
            day_name = date_obj.strftime("%A")

            day_stats[day_name]["total"] += 1

            # Track todo completion
            todos = entry.get("todos", {})
            if todos.get("completion_rate", 0) >= 0.8:
                day_stats[day_name]["completed"] += 1

            # Track habit completion
            habits = entry.get("habits", {})
            if habits.get("completion_rate") is not None:
                day_stats[day_name]["habit_rates"].append(habits["completion_rate"])

        except (ValueError, KeyError):
            continue

    # Calculate per-day averages
    by_day = {}
    for day, stats in day_stats.items():
        if stats["total"] > 0:
            by_day[day] = {
                "completion_rate": round(stats["completed"] / stats["total"], 2),
                "avg_habit_rate": round(sum(stats["habit_rates"]) / len(stats["habit_rates"]), 2) if stats["habit_rates"] else None,
                "sample_size": stats["total"]
            }

    # Identify weak days (< 50% completion rate with at least 2 data points)
    weak_days = [
        day for day, data in by_day.items()
        if data["completion_rate"] < 0.5 and data["sample_size"] >= 2
    ]

    return {"weak_days": weak_days, "by_day": by_day}


def compute_correlations(entries: list) -> dict:
    """
    Compute correlations between metrics.

    - Sleep hours → Morning mood
    - Morning mood → Todo completion
    - Sleep debt (< 7 hrs) → Next day performance

    Args:
        entries: List of daily metric entries

    Returns:
        dict with correlation coefficients and insights
    """
    recent = get_entries_for_days(entries, 30)

    if len(recent) < 5:
        return {
            "sleep_mood_correlation": None,
            "mood_completion_correlation": None,
            "insights": ["Not enough data for correlation analysis (need 5+ days)"]
        }

    # Pair up metrics for correlation
    sleep_mood_pairs = []
    mood_completion_pairs = []

    for entry in recent:
        sleep_hours = entry.get("sleep", {}).get("hours")
        morning_mood = entry.get("mood", {}).get("morning")
        todo_rate = entry.get("todos", {}).get("completion_rate")

        if sleep_hours and morning_mood:
            sleep_mood_pairs.append((sleep_hours, morning_mood))

        if morning_mood and todo_rate is not None:
            mood_completion_pairs.append((morning_mood, todo_rate))

    def pearson_correlation(pairs):
        """Simple Pearson correlation coefficient."""
        if len(pairs) < 3:
            return None

        n = len(pairs)
        x_vals = [p[0] for p in pairs]
        y_vals = [p[1] for p in pairs]

        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
        x_var = sum((x - x_mean) ** 2 for x in x_vals)
        y_var = sum((y - y_mean) ** 2 for y in y_vals)

        denominator = (x_var * y_var) ** 0.5
        if denominator == 0:
            return None

        return round(numerator / denominator, 2)

    sleep_mood_corr = pearson_correlation(sleep_mood_pairs)
    mood_completion_corr = pearson_correlation(mood_completion_pairs)

    # Generate insights
    insights = []

    if sleep_mood_corr is not None:
        if sleep_mood_corr > 0.5:
            insights.append("Strong positive correlation between sleep and mood - prioritize sleep!")
        elif sleep_mood_corr < -0.3:
            insights.append("Unexpected negative sleep-mood correlation - investigate other factors")

    if mood_completion_corr is not None:
        if mood_completion_corr > 0.5:
            insights.append("Morning mood strongly predicts daily success - start days with intention")
        elif mood_completion_corr < 0:
            insights.append("Low mood days may need reduced task load")

    return {
        "sleep_mood_correlation": sleep_mood_corr,
        "mood_completion_correlation": mood_completion_corr,
        "insights": insights if insights else ["No significant correlations detected"]
    }


def calculate_streaks(entries: list) -> dict:
    """
    Calculate current streak (consecutive days of compliance).

    Positive streak = consecutive days with >80% todo completion
    Negative streak = consecutive days with <50% todo completion

    Args:
        entries: List of daily metric entries

    Returns:
        dict with current_streak, longest_streak, and streak status
    """
    if not entries:
        return {"current_streak": 0, "longest_streak": 0, "status": "no_data"}

    # Sort by date descending (most recent first)
    sorted_entries = sorted(entries, key=lambda x: x.get("date", ""), reverse=True)

    current_streak = 0
    streak_positive = None

    for entry in sorted_entries:
        rate = entry.get("todos", {}).get("completion_rate")
        if rate is None:
            break

        if streak_positive is None:
            # First entry determines streak direction
            streak_positive = rate >= 0.5
            current_streak = 1 if streak_positive else -1
        elif streak_positive and rate >= 0.5:
            current_streak += 1
        elif not streak_positive and rate < 0.5:
            current_streak -= 1
        else:
            break

    # Calculate longest positive streak
    longest_streak = 0
    temp_streak = 0
    for entry in sorted(entries, key=lambda x: x.get("date", "")):
        rate = entry.get("todos", {}).get("completion_rate")
        if rate is not None and rate >= 0.8:
            temp_streak += 1
            longest_streak = max(longest_streak, temp_streak)
        else:
            temp_streak = 0

    status = "positive" if current_streak > 0 else "negative" if current_streak < 0 else "neutral"

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "status": status
    }


def get_recommended_todo_count(entries: list) -> int:
    """
    Determine optimal number of todos based on recent completion rates.

    - If completion rate < 50% over 7 days → 2 todos max
    - If completion rate 50-80% → 3 todos
    - If completion rate > 80% → 4-5 todos

    Args:
        entries: List of daily metric entries

    Returns:
        int: Recommended number of todos (2-5)
    """
    recent = get_entries_for_days(entries, 7)

    if not recent:
        return 3  # Default

    rates = [e["todos"]["completion_rate"] for e in recent if e.get("todos", {}).get("completion_rate") is not None]

    if not rates:
        return 3

    avg_rate = sum(rates) / len(rates)

    if avg_rate < 0.5:
        return 2
    elif avg_rate < 0.8:
        return 3
    else:
        return 4


def detect_warnings(entries: list) -> list:
    """
    Detect warning conditions that need attention.

    Args:
        entries: List of daily metric entries

    Returns:
        list: Warning messages for the LLM
    """
    warnings = []
    recent = get_entries_for_days(entries, 7)

    if not recent:
        return warnings

    # Check for sleep debt
    sleep_hours = [e["sleep"]["hours"] for e in recent if e.get("sleep", {}).get("hours")]
    if sleep_hours:
        avg_sleep = sum(sleep_hours) / len(sleep_hours)
        if avg_sleep < 6.5:
            warnings.append(f"Sleep debt accumulating: {avg_sleep:.1f}hr avg over {len(sleep_hours)} days (target: 7+)")

    # Check for declining mood trend
    moods = [e["mood"]["morning"] for e in recent if e.get("mood", {}).get("morning")]
    if len(moods) >= 3:
        recent_moods = moods[-3:]
        if all(m < 5 for m in recent_moods):
            warnings.append(f"Low mood streak: last 3 days averaged {sum(recent_moods)/3:.1f}/10")

    # Check for missed workouts
    workouts_missed = 0
    for entry in recent[-5:]:
        training = entry.get("training", {})
        if not training.get("activities") and not training.get("strength_exercises"):
            workouts_missed += 1
    if workouts_missed >= 3:
        warnings.append(f"Missed {workouts_missed} workouts in last 5 days")

    # Check for todo completion decline
    recent_rates = [e["todos"]["completion_rate"] for e in recent if e.get("todos", {}).get("completion_rate") is not None]
    if len(recent_rates) >= 3 and all(r < 0.5 for r in recent_rates[-3:]):
        warnings.append("Todo completion below 50% for 3+ days - consider reducing load")

    return warnings


def generate_llm_summary(full_context: bool = False) -> dict:
    """
    Generate a structured summary for the LLM prompt.

    Args:
        full_context: If True, include more detail for weekly planning

    Returns:
        dict: Structured metrics summary for LLM consumption
    """
    data = load_metrics()
    entries = data.get("entries", [])

    rolling_avg = compute_rolling_averages(entries)
    patterns = detect_day_of_week_patterns(entries)
    correlations = compute_correlations(entries)
    streaks = calculate_streaks(entries)
    warnings = detect_warnings(entries)
    recommended_todos = get_recommended_todo_count(entries)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "days_analyzed": rolling_avg["days_with_data"],
        "rolling_7day_averages": {
            "sleep_hours": rolling_avg["sleep_hours"],
            "sleep_quality": rolling_avg["sleep_quality"],
            "mood_morning": rolling_avg["mood_morning"],
            "mood_bedtime": rolling_avg["mood_bedtime"],
            "todo_completion_rate": rolling_avg["todo_completion_rate"],
            "habit_completion_rate": rolling_avg["habit_completion_rate"],
            "weight_lbs": rolling_avg["weight_lbs"]
        },
        "patterns": {
            "weak_days": patterns["weak_days"],
            "correlations": correlations
        },
        "streaks": streaks,
        "recommendations": {
            "max_todos": recommended_todos,
            "warnings": warnings
        }
    }

    if full_context:
        summary["patterns"]["by_day"] = patterns["by_day"]

    return summary


def get_recent_entries_summary(n_full: int = 3, n_summary: int = 4) -> dict:
    """
    Get recent entries in two tiers: full context and summarized.

    This implements the 7-day context approach:
    - Last 3 days: Full context for LLM
    - Days 4-7: Summarized metrics only

    Args:
        n_full: Number of days to include with full context
        n_summary: Number of additional days to summarize

    Returns:
        dict with full_context and summarized sections
    """
    data = load_metrics()
    entries = data.get("entries", [])

    # Sort by date descending
    sorted_entries = sorted(entries, key=lambda x: x.get("date", ""), reverse=True)

    # Split into tiers
    full_entries = sorted_entries[:n_full]
    summary_entries = sorted_entries[n_full:n_full + n_summary]

    # Full context: include most data
    full_context = []
    for entry in full_entries:
        full_context.append({
            "date": entry.get("date"),
            "sleep": entry.get("sleep"),
            "mood": entry.get("mood"),
            "weight_lbs": entry.get("weight_lbs"),
            "training": entry.get("training"),
            "todos": entry.get("todos"),
            "habits": entry.get("habits"),
            "nutrition": {
                "calories": entry.get("nutrition", {}).get("calories"),
                "protein_g": entry.get("nutrition", {}).get("protein_g")
            }
        })

    # Summarized: just key metrics
    summarized = []
    for entry in summary_entries:
        summarized.append({
            "date": entry.get("date"),
            "sleep_hours": entry.get("sleep", {}).get("hours"),
            "mood_morning": entry.get("mood", {}).get("morning"),
            "todo_completion": entry.get("todos", {}).get("completion_rate"),
            "workout_type": entry.get("training", {}).get("workout_type")
        })

    return {
        "full_context": full_context,
        "summarized": summarized
    }


if __name__ == "__main__":
    # Test the analyzer
    print("Testing metrics analyzer...")
    print("\n=== LLM Summary ===")
    summary = generate_llm_summary(full_context=True)
    print(json.dumps(summary, indent=2))

    print("\n=== Recent Entries (7-day tiered) ===")
    recent = get_recent_entries_summary()
    print(json.dumps(recent, indent=2))
