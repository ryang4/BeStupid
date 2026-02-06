"""
Unified Brain Dashboard - Complete life overview in one place.

Aggregates data from all systems:
- Today's schedule and free time
- Recovery metrics and training readiness
- Key relationships to follow up on
- Financial health
- Recent biomarkers
- Active goals progress
- Smart nudges and alerts

Usage:
    python brain.py              # Show full dashboard
    python brain.py --compact    # Compact view
    python brain.py --json       # JSON output for Telegram bot
"""

import os
import sys
import json
import re
from datetime import datetime

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def safe_call(func, default=None):
    """Safely call a function, returning default if it fails."""
    try:
        return func()
    except Exception as e:
        return default


def get_recovery_status() -> dict:
    """Get recovery and training readiness."""
    try:
        from garmin_sync import get_latest_recovery
        return get_latest_recovery() or {}
    except:
        return {}


def get_calendar_status() -> dict:
    """Get today's calendar overview."""
    try:
        from calendar_sync import get_schedule_summary
        return get_schedule_summary() or {}
    except:
        return {}


def get_crm_status() -> dict:
    """Get relationship status."""
    try:
        from crm import get_overdue_contacts, get_upcoming_birthdays
        overdue = get_overdue_contacts()
        birthdays = get_upcoming_birthdays(7)
        return {
            "overdue_count": len(overdue),
            "top_overdue": overdue[:3],
            "upcoming_birthdays": birthdays
        }
    except:
        return {}


def get_finance_status() -> dict:
    """Get financial overview."""
    try:
        from finance import get_financial_summary
        return get_financial_summary() or {}
    except:
        return {}


def get_goals_status() -> dict:
    """Get active goals progress."""
    try:
        from reviews import get_active_goals
        return get_active_goals() or {}
    except:
        return {}


def get_nudges() -> dict:
    """Get all smart nudges."""
    try:
        from notifications import get_all_nudges, get_priority_nudges
        return {
            "all": get_all_nudges(),
            "priority": get_priority_nudges(5)
        }
    except:
        return {"all": {}, "priority": []}


def get_memory_status() -> dict:
    """Get memory system status."""
    try:
        from memory import MEMORY_ROOT, query_events
        counts = {}
        for category in ["people", "projects", "decisions", "commitments"]:
            cat_dir = MEMORY_ROOT / category
            counts[category] = len(list(cat_dir.glob("*.json"))) if cat_dir.exists() else 0
        recent = query_events(limit=5)
        last_event_ts = recent[-1]["ts"] if recent else None
        return {
            "counts": counts,
            "total": sum(counts.values()),
            "last_event": last_event_ts,
            "recent_events": len(query_events(limit=1000)),
        }
    except Exception:
        return {}


def get_todays_log_status() -> dict:
    """Check if today's log has been filled out."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "content", "logs")
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(log_dir, f"{today}.md")

    if not os.path.exists(log_path):
        return {"exists": False, "filled": False, "command_engine": {}, "todos": {"completed": 0, "total": 0, "rate": 0.0}}

    try:
        with open(log_path, 'r') as f:
            content = f.read()

        def extract_section(full_text: str, heading: str) -> str:
            if heading not in full_text:
                return ""
            section = full_text.split(heading, 1)[1]
            next_idx = section.find("\n## ")
            return section[:next_idx] if next_idx != -1 else section

        def extract_subsection(full_text: str, heading: str) -> str:
            if heading not in full_text:
                return ""
            section = full_text.split(heading, 1)[1]
            next_idx = section.find("\n### ")
            return section[:next_idx] if next_idx != -1 else section

        def parse_checkboxes(section_text: str) -> tuple[int, int]:
            checked = 0
            total = 0
            for raw in section_text.splitlines():
                line = raw.strip()
                if line.startswith("- [x]"):
                    checked += 1
                    total += 1
                elif line.startswith("- [ ]"):
                    total += 1
            return checked, total

        # Check if key fields are filled
        filled_fields = 0
        total_fields = 4

        if "Weight::" in content and len(content.split("Weight::")[1].split("\n")[0].strip()) > 0:
            filled_fields += 1
        if "Sleep::" in content and len(content.split("Sleep::")[1].split("\n")[0].strip()) > 0:
            filled_fields += 1
        if "Mood_AM::" in content and len(content.split("Mood_AM::")[1].split("\n")[0].strip()) > 0:
            filled_fields += 1
        if "Energy::" in content and len(content.split("Energy::")[1].split("\n")[0].strip()) > 0:
            filled_fields += 1

        # Parse command engine section
        command_engine = {
            "workload_tier": None,
            "capacity_score": None,
            "signals": [],
            "must_win": [],
            "can_do": [],
            "not_today": [],
        }
        ce_section = extract_section(content, "## Command Engine")
        if ce_section:
            tier_match = re.search(r"^Workload_Tier::\s*(.+)$", ce_section, re.MULTILINE)
            if tier_match:
                command_engine["workload_tier"] = tier_match.group(1).strip()

            cap_match = re.search(r"^Capacity_Score::\s*(\d+)", ce_section, re.MULTILINE)
            if cap_match:
                try:
                    command_engine["capacity_score"] = int(cap_match.group(1))
                except ValueError:
                    pass

            if "**Readiness Signals:**" in ce_section:
                signal_block = ce_section.split("**Readiness Signals:**", 1)[1]
                signal_block = signal_block.split("### ", 1)[0]
                for raw in signal_block.splitlines():
                    line = raw.strip()
                    if line.startswith("- "):
                        command_engine["signals"].append(line[2:].strip())

            for raw in extract_subsection(ce_section, "### Must Win 3").splitlines():
                line = raw.strip()
                if line.startswith("- [ ] ") or line.startswith("- [x] "):
                    command_engine["must_win"].append(line[6:].strip())

            for raw in extract_subsection(ce_section, "### Can Do 2").splitlines():
                line = raw.strip()
                if line.startswith("- [ ] ") or line.startswith("- [x] "):
                    command_engine["can_do"].append(line[6:].strip())

            for raw in extract_subsection(ce_section, "### Not Today").splitlines():
                line = raw.strip()
                if line.startswith("- "):
                    command_engine["not_today"].append(line[2:].strip())

        # Parse execution todos (only Today's Todos section)
        todos_section = extract_section(content, "## Today's Todos")
        todos_completed, todos_total = parse_checkboxes(todos_section)
        todo_rate = round(todos_completed / todos_total, 2) if todos_total else 0.0

        return {
            "exists": True,
            "filled": filled_fields >= 2,
            "completion": round(filled_fields / total_fields * 100, 0),
            "command_engine": command_engine,
            "todos": {
                "completed": todos_completed,
                "total": todos_total,
                "rate": todo_rate,
            },
        }
    except:
        return {"exists": True, "filled": False, "command_engine": {}, "todos": {"completed": 0, "total": 0, "rate": 0.0}}


def get_morning_briefing_data() -> dict:
    """
    Get data for morning briefing (Telegram-optimized).

    Returns structured data for morning message:
    - Recovery status (score, sleep, HRV, recommendation)
    - Today's workout from protocol
    - Schedule overview (events, next meeting, deep work blocks)
    - Top 3 priority nudges
    """
    data = get_full_dashboard()

    # Recovery section
    recovery_data = data.get("recovery", {})
    recovery = {
        "score": None,
        "status": "unknown",
        "sleep_hours": None,
        "sleep_score": None,
        "hrv": None,
        "hrv_status": None,
        "recommendation": "No recovery data available"
    }

    if recovery_data.get("recovery", {}).get("score"):
        rec = recovery_data["recovery"]
        recovery["score"] = rec["score"]
        recovery["status"] = rec.get("status", "unknown")
        recovery["sleep_hours"] = recovery_data.get("sleep_hours")
        recovery["sleep_score"] = recovery_data.get("sleep_score")
        recovery["hrv"] = recovery_data.get("hrv")
        recovery["hrv_status"] = recovery_data.get("hrv_status")

        # Get first recommendation
        if rec.get("recommendations"):
            recovery["recommendation"] = rec["recommendations"][0]

    # Workout from today's log
    workout = "No workout planned"
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "content", "logs")
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(log_dir, f"{today}.md")

    if os.path.exists(log_path):
        try:
            with open(log_path, 'r') as f:
                content = f.read()
            if "## Planned Workout" in content:
                workout_section = content.split("## Planned Workout")[1].split("\n\n")[0]
                workout = workout_section.strip()
        except:
            pass

    # Schedule
    calendar = data.get("calendar", {})
    schedule = {
        "events_count": calendar.get("total_events", 0),
        "next_event": None,
        "deep_work_blocks": []
    }

    if calendar.get("next_meeting"):
        nm = calendar["next_meeting"]
        schedule["next_event"] = f"{nm['title']} at {nm['time']} ({nm.get('duration', 'N/A')})"

    if calendar.get("free_blocks"):
        # Find blocks > 90 minutes (deep work threshold)
        for block in calendar["free_blocks"]:
            if block.get("duration_minutes", 0) >= 90:
                schedule["deep_work_blocks"].append(
                    f"{block['start']}-{block['end']} ({block['duration_minutes']}min)"
                )

    # Priorities: command engine must-win tasks take precedence.
    command_engine = data.get("todays_log", {}).get("command_engine", {})
    must_win = command_engine.get("must_win", [])
    if must_win:
        priorities = must_win[:3]
    else:
        priorities = data.get("nudges", {}).get("priority", [])[:3]

    return {
        "recovery": recovery,
        "workout": workout,
        "schedule": schedule,
        "priorities": priorities
    }


def get_evening_reflection_data() -> dict:
    """
    Get data for evening reflection (Telegram-optimized).

    Returns structured data for evening message:
    - Todo completion rate
    - Metrics filled vs missing
    - Tomorrow's preview
    """
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "content", "logs")
    log_path = os.path.join(log_dir, f"{today}.md")

    result = {
        "completion": {"completed": 0, "total": 0, "rate": 0.0},
        "metrics_filled": [],
        "metrics_missing": [],
        "tomorrow_preview": "Check /brain for tomorrow's schedule"
    }

    if not os.path.exists(log_path):
        return result

    try:
        with open(log_path, 'r') as f:
            content = f.read()

        # Calculate todo completion from execution section only.
        todos_total = 0
        todos_completed = 0
        if "## Today's Todos" in content:
            todos_section = content.split("## Today's Todos", 1)[1]
            next_section = todos_section.find("\n## ")
            if next_section != -1:
                todos_section = todos_section[:next_section]

            for raw in todos_section.splitlines():
                line = raw.strip()
                if line.startswith("- [x]"):
                    todos_completed += 1
                    todos_total += 1
                elif line.startswith("- [ ]"):
                    todos_total += 1

        if todos_total > 0:
            result["completion"] = {
                "completed": todos_completed,
                "total": todos_total,
                "rate": round(todos_completed / todos_total, 2)
            }

        # Check which metrics are filled
        metric_fields = ["Weight", "Sleep", "Sleep_Quality", "Mood_AM", "Mood_PM", "Energy", "Focus"]

        for field in metric_fields:
            import re
            match = re.search(rf"^{field}::\s*(.+)$", content, re.MULTILINE)
            if match and match.group(1).strip():
                result["metrics_filled"].append(field)
            else:
                result["metrics_missing"].append(field)

        # Tomorrow preview (get tomorrow's workout from protocol)
        from datetime import timedelta
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow_day = tomorrow.strftime("%A")

        # Try to get protocol
        days_since_monday = datetime.now().weekday()
        from datetime import timedelta
        monday = datetime.now() - timedelta(days=days_since_monday)
        monday_str = monday.strftime("%Y-%m-%d")
        protocol_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "content", "config", f"protocol_{monday_str}.md"
        )

        if os.path.exists(protocol_path):
            with open(protocol_path, 'r') as f:
                protocol_content = f.read()

            if "## Weekly Schedule" in protocol_content:
                schedule_section = protocol_content.split("## Weekly Schedule")[1]
                if "\n## " in schedule_section:
                    schedule_section = schedule_section.split("\n## ")[0]

                for line in schedule_section.split("\n"):
                    if tomorrow_day in line:
                        result["tomorrow_preview"] = line.strip()
                        break

    except Exception as e:
        pass

    return result


def get_full_dashboard() -> dict:
    """Get complete dashboard data."""
    return {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "day": datetime.now().strftime("%A"),
        "recovery": safe_call(get_recovery_status, {}),
        "calendar": safe_call(get_calendar_status, {}),
        "crm": safe_call(get_crm_status, {}),
        "finance": safe_call(get_finance_status, {}),
        "goals": safe_call(get_goals_status, {}),
        "nudges": safe_call(get_nudges, {"all": {}, "priority": []}),
        "todays_log": safe_call(get_todays_log_status, {}),
        "memory": safe_call(get_memory_status, {})
    }


def format_dashboard_compact() -> str:
    """Format dashboard in compact view."""
    data = get_full_dashboard()

    lines = []
    lines.append(f"{'='*50}")
    lines.append(f"BRAIN DASHBOARD - {data['day']}, {data['date']}")
    lines.append(f"{'='*50}\n")

    # Recovery
    recovery = data.get("recovery", {})
    if recovery.get("recovery", {}).get("score"):
        score = recovery["recovery"]["score"]
        status = recovery["recovery"].get("status", "unknown")
        lines.append(f"💪 Recovery: {score}/100 ({status})")
    else:
        lines.append("💪 Recovery: No data")

    # Calendar
    calendar = data.get("calendar", {})
    if calendar.get("total_events") is not None:
        events = calendar["total_events"]
        meetings = calendar.get("total_meeting_hours", 0)
        free = calendar.get("total_free_hours", 0)
        lines.append(f"📅 Today: {events} events, {meetings:.1f}h meetings, {free:.1f}h free")

        if calendar.get("next_meeting"):
            nm = calendar["next_meeting"]
            lines.append(f"   Next: {nm['title']} at {nm['time']}")
    else:
        lines.append("📅 Calendar: Not synced")

    # CRM
    crm = data.get("crm", {})
    overdue = crm.get("overdue_count", 0)
    if overdue > 0:
        lines.append(f"👥 Relationships: {overdue} overdue follow-ups")
    else:
        lines.append("👥 Relationships: All caught up")

    # Finance
    finance = data.get("finance", {})
    biz = finance.get("business", {}).get("current", {})
    if biz.get("runway_months"):
        lines.append(f"💰 Business: {biz['runway_months']:.1f} months runway")

    # Goals
    goals = data.get("goals", {})
    if goals.get("active_count"):
        lines.append(f"🎯 Goals: {goals['active_count']} active")

    # Today's Log
    log = data.get("todays_log", {})
    if log.get("exists"):
        if log.get("filled"):
            lines.append(f"📝 Log: {log['completion']:.0f}% complete")
        else:
            lines.append("📝 Log: Not filled yet")
        todo_meta = log.get("todos", {})
        if todo_meta.get("total", 0) > 0:
            lines.append(f"✅ Execution: {todo_meta['completed']}/{todo_meta['total']}")
    else:
        lines.append("📝 Log: Not created")

    command_engine = log.get("command_engine", {})
    if command_engine.get("must_win"):
        lines.append("🎯 Must Win:")
        for task in command_engine["must_win"][:2]:
            lines.append(f"   - {task}")
        if command_engine.get("workload_tier"):
            lines.append(f"   Tier: {command_engine['workload_tier']}")

    # Memory
    memory = data.get("memory", {})
    if memory.get("total"):
        lines.append(f"🧠 Memory: {memory['total']} records, {memory.get('recent_events', 0)} events")
    else:
        lines.append("🧠 Memory: Empty")

    # Priority Nudges
    nudges = data.get("nudges", {}).get("priority", [])
    if nudges:
        lines.append(f"\n⚡ TOP PRIORITIES:")
        for i, nudge in enumerate(nudges[:3], 1):
            lines.append(f"   {i}. {nudge}")

    return "\n".join(lines)


def format_dashboard_full() -> str:
    """Format dashboard in full view."""
    data = get_full_dashboard()

    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"{'BRAIN DASHBOARD':^60}")
    lines.append(f"{data['day']}, {data['date']:^60}")
    lines.append(f"{'='*60}\n")

    # === RECOVERY & TRAINING ===
    lines.append("💪 RECOVERY & TRAINING")
    recovery = data.get("recovery", {})

    if recovery.get("recovery", {}).get("score"):
        rec = recovery["recovery"]
        lines.append(f"   Score: {rec['score']}/100 ({rec.get('status', 'unknown')})")

        if rec.get("recommendations"):
            for rec_text in rec["recommendations"][:2]:
                lines.append(f"   → {rec_text}")

        if recovery.get("sleep_hours"):
            lines.append(f"   Sleep: {recovery['sleep_hours']}h (score: {recovery.get('sleep_score', 'N/A')})")

        if recovery.get("hrv"):
            lines.append(f"   HRV: {recovery['hrv']} ({recovery.get('hrv_status', 'N/A')})")

        if recovery.get("body_battery"):
            lines.append(f"   Body Battery: {recovery['body_battery']}")

    else:
        lines.append("   No Garmin data synced yet")

    # === CALENDAR ===
    lines.append("\n📅 CALENDAR")
    calendar = data.get("calendar", {})

    if calendar.get("total_events") is not None:
        lines.append(f"   Events: {calendar['total_events']}")
        lines.append(f"   Meetings: {calendar.get('total_meeting_hours', 0):.1f}h")
        lines.append(f"   Free Time: {calendar.get('total_free_hours', 0):.1f}h")

        if calendar.get("longest_free_block"):
            lb = calendar["longest_free_block"]
            lines.append(f"   Longest Block: {lb['start']}-{lb['end']} ({lb['duration_minutes']}min)")

        if calendar.get("next_meeting"):
            nm = calendar["next_meeting"]
            lines.append(f"   Next: {nm['title']} at {nm['time']} ({nm['minutes_until']}min)")

        if calendar.get("deep_work_available"):
            lines.append("   ✅ Deep work block available")
        else:
            lines.append("   ⚠️ No deep work blocks")
    else:
        lines.append("   Not synced")

    # === RELATIONSHIPS ===
    lines.append("\n👥 RELATIONSHIPS")
    crm = data.get("crm", {})

    overdue_count = crm.get("overdue_count", 0)
    if overdue_count > 0:
        lines.append(f"   {overdue_count} overdue follow-ups:")
        for contact in crm.get("top_overdue", [])[:3]:
            lines.append(f"   • {contact['name']} ({contact['days_since_contact']}d ago)")
    else:
        lines.append("   ✅ All caught up")

    birthdays = crm.get("upcoming_birthdays", [])
    if birthdays:
        lines.append("   Upcoming birthdays:")
        for bday in birthdays[:2]:
            lines.append(f"   🎂 {bday['name']} in {bday['days_until']}d")

    # === FINANCE ===
    lines.append("\n💰 FINANCE")
    finance = data.get("finance", {})

    biz = finance.get("business", {}).get("current", {})
    if biz:
        if biz.get("mrr"):
            lines.append(f"   MRR: ${biz['mrr']:,.0f}")
        if biz.get("runway_months"):
            status = "⚠️" if biz["runway_months"] < 6 else "✅"
            lines.append(f"   {status} Runway: {biz['runway_months']:.1f} months")

    personal = finance.get("personal", {}).get("current", {})
    if personal:
        if personal.get("net_worth"):
            lines.append(f"   Net Worth: ${personal['net_worth']:,.0f}")
        if personal.get("savings_rate"):
            lines.append(f"   Savings Rate: {personal['savings_rate']*100:.0f}%")

    # === GOALS ===
    lines.append("\n🎯 GOALS")
    goals = data.get("goals", {})

    if goals.get("active"):
        lines.append(f"   {len(goals['active'])} active goals:")
        for goal in goals['active'][:3]:
            progress = goal.get("progress", 0) * 100
            lines.append(f"   • {goal['name']}: {progress:.0f}%")
    else:
        lines.append("   No active goals")

    # === TODAY'S LOG ===
    lines.append("\n📝 TODAY'S LOG")
    log = data.get("todays_log", {})

    if log.get("exists"):
        if log.get("filled"):
            lines.append(f"   ✅ {log['completion']:.0f}% complete")
        else:
            lines.append("   ⚠️ Not filled out yet")
        todo_meta = log.get("todos", {})
        if todo_meta.get("total", 0) > 0:
            lines.append(f"   Execution: {todo_meta['completed']}/{todo_meta['total']} ({int(todo_meta['rate']*100)}%)")
    else:
        lines.append("   ❌ Not created yet")

    command_engine = log.get("command_engine", {})
    if command_engine.get("must_win"):
        lines.append("\n🚀 COMMAND ENGINE")
        if command_engine.get("workload_tier"):
            tier = command_engine["workload_tier"]
            capacity = command_engine.get("capacity_score")
            capacity_txt = f" | Capacity {capacity}/5" if capacity else ""
            lines.append(f"   Tier: {tier}{capacity_txt}")
        lines.append("   Must Win 3:")
        for task in command_engine["must_win"][:3]:
            lines.append(f"   • {task}")
        if command_engine.get("not_today"):
            lines.append("   Not Today:")
            for task in command_engine["not_today"][:2]:
                lines.append(f"   - {task}")

    # === MEMORY ===
    lines.append("\n🧠 MEMORY")
    memory = data.get("memory", {})
    if memory.get("total"):
        counts = memory.get("counts", {})
        lines.append(f"   Total: {memory['total']} records")
        lines.append(f"   People: {counts.get('people', 0)} | Projects: {counts.get('projects', 0)} | Decisions: {counts.get('decisions', 0)} | Commitments: {counts.get('commitments', 0)}")
        lines.append(f"   Events logged: {memory.get('recent_events', 0)}")
        if memory.get("last_event"):
            lines.append(f"   Last activity: {memory['last_event']}")
    else:
        lines.append("   No memory data yet")

    # === PRIORITY NUDGES ===
    nudges = data.get("nudges", {}).get("priority", [])
    if nudges:
        lines.append("\n⚡ PRIORITY NUDGES")
        for i, nudge in enumerate(nudges, 1):
            lines.append(f"   {i}. {nudge}")

    lines.append(f"\n{'='*60}\n")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Unified brain dashboard")
    parser.add_argument("--compact", action="store_true", help="Compact view")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.json:
        data = get_full_dashboard()
        print(json.dumps(data, indent=2))
    elif args.compact:
        print(format_dashboard_compact())
    else:
        print(format_dashboard_full())
