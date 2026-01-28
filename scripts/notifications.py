"""
Smart Notification Engine - Proactive nudges based on patterns and context.

Analyzes:
- Calendar conflicts with training
- Recovery metrics vs planned intensity
- Relationship follow-ups
- Financial alerts
- Biomarker trends
- Supplement compliance
- Goal deadlines
- Pattern-based reminders

Generates context-aware nudges for daily briefing.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def safe_import(module_name: str, function_name: str):
    """Safely import a function, returning None if unavailable."""
    try:
        module = __import__(module_name)
        return getattr(module, function_name, None)
    except (ImportError, AttributeError):
        return None


def get_all_nudges() -> dict:
    """
    Collect nudges from all systems.

    Returns:
        dict with nudges by category
    """
    nudges = {
        "recovery": [],
        "calendar": [],
        "relationships": [],
        "finance": [],
        "health": [],
        "goals": [],
        "patterns": []
    }

    # === RECOVERY & TRAINING ===
    try:
        from garmin_sync import get_latest_recovery, generate_training_recommendations
        recovery = get_latest_recovery()
        if recovery:
            recs = generate_training_recommendations()
            nudges["recovery"].extend(recs)

            # Add recovery score to nudge if low
            if recovery.get("recovery", {}).get("score") and recovery["recovery"]["score"] < 50:
                nudges["recovery"].append(f"Low recovery score: {recovery['recovery']['score']}/100")

    except (ImportError, Exception) as e:
        pass

    # === CALENDAR ===
    try:
        from calendar_sync import get_schedule_summary, get_meeting_prep_reminders
        
        schedule = get_schedule_summary()
        
        # Next meeting reminder
        if schedule.get("next_meeting"):
            nm = schedule["next_meeting"]
            if nm["minutes_until"] < 30:
                nudges["calendar"].append(f"Meeting in {nm['minutes_until']}min: {nm['title']}")

        # Heavy meeting day
        if schedule.get("total_meeting_hours", 0) > 5:
            nudges["calendar"].append(f"Heavy meeting day: {schedule['total_meeting_hours']}h scheduled")

        # No deep work blocks
        if not schedule.get("deep_work_available"):
            nudges["calendar"].append("No deep work blocks today - consider blocking time")

        # Meeting prep
        prep_reminders = get_meeting_prep_reminders(schedule.get("events", []))
        for prep in prep_reminders[:2]:
            if prep["prep_items"]:
                nudges["calendar"].append(f"Prep for {prep['event']}: {', '.join(prep['prep_items'][:2])}")

    except (ImportError, Exception):
        pass

    # === RELATIONSHIPS ===
    try:
        from crm import generate_crm_nudges
        crm_nudges = generate_crm_nudges()
        nudges["relationships"].extend(crm_nudges[:3])  # Limit to top 3
    except (ImportError, Exception):
        pass

    # === FINANCE ===
    try:
        from finance import generate_finance_nudges
        finance_nudges = generate_finance_nudges()
        nudges["finance"].extend(finance_nudges[:2])
    except (ImportError, Exception):
        pass

    # === HEALTH ===
    try:
        from biomarkers import generate_biomarker_nudges
        bio_nudges = generate_biomarker_nudges()
        nudges["health"].extend(bio_nudges)
    except (ImportError, Exception):
        pass

    try:
        from supplements import generate_supplement_nudges
        supp_nudges = generate_supplement_nudges()
        nudges["health"].extend(supp_nudges[:2])
    except (ImportError, Exception):
        pass

    # === GOALS ===
    try:
        from reviews import get_goal_progress_nudges
        goal_nudges = get_goal_progress_nudges()
        nudges["goals"].extend(goal_nudges[:3])
    except (ImportError, Exception):
        pass

    # === PATTERN-BASED REMINDERS ===
    try:
        from metrics_analyzer import generate_llm_summary
        metrics = generate_llm_summary(full_context=False)

        # Sleep pattern
        sleep_avg = metrics.get("7_day_averages", {}).get("sleep_hours")
        if sleep_avg and sleep_avg < 6.5:
            nudges["patterns"].append(f"Sleep trending low: {sleep_avg:.1f}h avg last 7 days")

        # Todo completion pattern
        completion_avg = metrics.get("7_day_averages", {}).get("completion_rate")
        if completion_avg and completion_avg < 0.6:
            nudges["patterns"].append(f"Todo completion trending low: {completion_avg*100:.0f}% - consider reducing daily load")

        # Mood pattern
        mood_avg = metrics.get("7_day_averages", {}).get("mood_avg")
        if mood_avg and mood_avg < 4:
            nudges["patterns"].append(f"Mood trending low: {mood_avg:.1f}/10 avg - prioritize self-care")

    except (ImportError, Exception):
        pass

    return nudges


def get_priority_nudges(max_nudges: int = 5) -> List[str]:
    """
    Get prioritized list of most important nudges.

    Prioritizes by urgency and importance.
    """
    all_nudges = get_all_nudges()

    # Priority order: recovery > calendar > health > relationships > finance > patterns > goals
    priority_order = ["recovery", "calendar", "health", "relationships", "finance", "patterns", "goals"]

    prioritized = []

    for category in priority_order:
        prioritized.extend(all_nudges.get(category, []))

        if len(prioritized) >= max_nudges:
            break

    return prioritized[:max_nudges]


def format_nudges_for_briefing() -> str:
    """Format nudges as text for daily briefing."""
    all_nudges = get_all_nudges()

    lines = []

    # Show by category
    categories = {
        "recovery": "💪 Recovery & Training",
        "calendar": "📅 Calendar",
        "relationships": "👥 Relationships",
        "finance": "💰 Finance",
        "health": "🏥 Health",
        "goals": "🎯 Goals",
        "patterns": "📊 Patterns"
    }

    for category, title in categories.items():
        nudges = all_nudges.get(category, [])
        if nudges:
            lines.append(f"\n{title}:")
            for nudge in nudges[:3]:  # Max 3 per category
                lines.append(f"  • {nudge}")

    if not any(all_nudges.values()):
        lines.append("No nudges today - you're on track!")

    return "\n".join(lines)


def get_critical_alerts() -> List[str]:
    """
    Get only critical alerts that require immediate attention.

    Returns:
        List of critical alert strings
    """
    alerts = []
    all_nudges = get_all_nudges()

    # Check for critical keywords
    critical_keywords = ["urgent", "critical", "runway", "overdue", "warning", "low recovery"]

    for category_nudges in all_nudges.values():
        for nudge in category_nudges:
            if any(keyword in nudge.lower() for keyword in critical_keywords):
                alerts.append(nudge)

    return alerts


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Smart notification engine")
    parser.add_argument("--critical", action="store_true", help="Show only critical alerts")
    parser.add_argument("--top", type=int, default=5, help="Number of top nudges to show")
    args = parser.parse_args()

    if args.critical:
        alerts = get_critical_alerts()
        print("\n=== Critical Alerts ===")
        if alerts:
            for alert in alerts:
                print(f"  ⚠️  {alert}")
        else:
            print("  No critical alerts")
    else:
        print(format_nudges_for_briefing())
