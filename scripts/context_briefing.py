#!/usr/bin/env python3
"""
Context Briefing - Quick summary of Ryan's current state, goals, and recent activity

Provides a snapshot for the AI assistant to quickly get context on:
- Current goals and priorities
- Recent habits and compliance
- Active projects and blockers
- Recent conversation topics
- Today's plan and todos

Usage:
    python context_briefing.py [--full]
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

PROJECT_ROOT = Path(__file__).parent.parent


def get_current_goals():
    """Get active projects and their priorities."""
    projects_dir = PROJECT_ROOT / "content" / "projects"

    if not projects_dir.exists():
        return []

    goals = []
    for project_file in projects_dir.glob("*.md"):
        try:
            content = project_file.read_text()
            lines = content.split("\n")

            # Parse frontmatter
            title = ""
            status = ""
            priority = 0
            target_date = ""

            in_frontmatter = False
            for line in lines:
                if line.strip() == "---":
                    in_frontmatter = not in_frontmatter
                    continue

                if in_frontmatter:
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"')
                    elif line.startswith("status:"):
                        status = line.split(":", 1)[1].strip()
                    elif line.startswith("priority:"):
                        priority = int(line.split(":", 1)[1].strip())
                    elif line.startswith("target_date:"):
                        target_date = line.split(":", 1)[1].strip()

            if status == "active":
                goals.append({
                    "title": title,
                    "priority": priority,
                    "target": target_date,
                    "file": project_file.name
                })
        except:
            pass

    # Sort by priority
    goals.sort(key=lambda x: x["priority"])
    return goals


def get_current_habits():
    """Get configured daily habits."""
    habits_file = PROJECT_ROOT / "content" / "config" / "habits.md"

    if not habits_file.exists():
        return []

    try:
        content = habits_file.read_text()
        habits = []

        # Simple parsing - look for habit names
        in_habits = False
        for line in content.split("\n"):
            if "name:" in line:
                name = line.split(":", 1)[1].strip().strip('"')
                habits.append(name)

        return habits
    except:
        return []


def get_recent_logs(days=3):
    """Get summary of recent daily logs."""
    logs_dir = PROJECT_ROOT / "content" / "logs"

    if not logs_dir.exists():
        return []

    recent = []
    for i in range(days):
        date = datetime.now() - timedelta(days=i)
        log_file = logs_dir / f"{date.strftime('%Y-%m-%d')}.md"

        if log_file.exists():
            try:
                content = log_file.read_text()

                # Extract key info
                todos_done = content.count("- [x]")
                todos_total = content.count("- [ ]") + todos_done

                # Check if workout was done
                workout_done = "- [x] Perform today's workout" in content or "- [x] workout" in content.lower()

                recent.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "todos": f"{todos_done}/{todos_total}",
                    "workout": "✓" if workout_done else "✗"
                })
            except:
                pass

    return recent


def get_todays_plan():
    """Get today's log and todos."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = PROJECT_ROOT / "content" / "logs" / f"{today}.md"

    if not log_file.exists():
        return {"exists": False}

    try:
        content = log_file.read_text()

        # Extract todos
        todos = []
        in_todos = False
        for line in content.split("\n"):
            if "## Today's Todos" in line:
                in_todos = True
                continue
            elif line.startswith("## ") and in_todos:
                break
            elif in_todos and line.strip().startswith("- "):
                todos.append(line.strip())

        # Extract Top 3
        top_3 = []
        in_top3 = False
        for line in content.split("\n"):
            if "## Top 3 for Tomorrow" in line:
                in_top3 = True
                continue
            elif in_top3 and line.strip() and not line.startswith("<!--"):
                if line.strip().startswith(("1.", "2.", "3.")):
                    top_3.append(line.strip())

        # Extract planned workout
        workout = ""
        in_workout = False
        for line in content.split("\n"):
            if "## Planned Workout" in line:
                in_workout = True
                continue
            elif line.startswith("## ") and in_workout:
                break
            elif in_workout and line.strip():
                workout += line.strip() + " "

        return {
            "exists": True,
            "todos": todos,
            "top_3": top_3,
            "workout": workout.strip()[:100] + "..." if len(workout) > 100 else workout.strip()
        }
    except:
        return {"exists": False}


def get_memory_context():
    """Get key info from memory system."""
    memory_dir = PROJECT_ROOT / "memory"

    context = {
        "people": 0,
        "projects": 0,
        "decisions": 0,
        "commitments": 0
    }

    if not memory_dir.exists():
        return context

    try:
        for key in context.keys():
            file = memory_dir / f"{key}.json"
            if file.exists():
                data = json.loads(file.read_text())
                context[key] = len(data)
    except:
        pass

    return context


def generate_briefing(full=False):
    """Generate context briefing."""
    output = []

    output.append("=" * 60)
    output.append("CONTEXT BRIEFING - Ryan's Current State")
    output.append("=" * 60)
    output.append("")

    # Goals
    output.append("📊 ACTIVE GOALS (by priority):")
    goals = get_current_goals()
    if goals:
        for goal in goals:
            output.append(f"  {goal['priority']}. {goal['title']} (target: {goal['target']})")
    else:
        output.append("  No active projects found")
    output.append("")

    # Current habits
    output.append("✅ DAILY HABITS:")
    habits = get_current_habits()
    if habits:
        for habit in habits:
            output.append(f"  • {habit}")
    else:
        output.append("  No habits configured")
    output.append("")

    # Today's plan
    output.append("📅 TODAY'S PLAN:")
    today = get_todays_plan()
    if today.get("exists"):
        if today.get("workout"):
            output.append(f"  Workout: {today['workout']}")
        if today.get("todos"):
            output.append("  Todos:")
            for todo in today["todos"][:5]:
                output.append(f"    {todo}")
        if today.get("top_3") and any(t.strip() != t.split('.', 1)[0] + '.' for t in today["top_3"]):
            output.append("  Top 3 priorities (from yesterday):")
            for item in today["top_3"]:
                output.append(f"    {item}")
    else:
        output.append("  No log created yet for today")
    output.append("")

    # Recent activity
    if full:
        output.append("📈 RECENT ACTIVITY (last 3 days):")
        recent = get_recent_logs(3)
        if recent:
            for day in recent:
                output.append(f"  {day['date']}: Todos {day['todos']}, Workout {day['workout']}")
        output.append("")

    # Memory system
    memory = get_memory_context()
    output.append("🧠 MEMORY SYSTEM:")
    output.append(f"  People: {memory['people']} | Projects: {memory['projects']} | "
                 f"Decisions: {memory['decisions']} | Commitments: {memory['commitments']}")
    output.append("")

    # Key file locations
    output.append("📁 KEY LOCATIONS:")
    output.append("  • Projects: content/projects/*.md")
    output.append("  • Habits: content/config/habits.md")
    output.append("  • Daily logs: content/logs/YYYY-MM-DD.md")
    output.append("  • Memory: memory/*.json")
    output.append("  • Weekly protocol: content/config/protocol_*.md")
    output.append("")

    output.append("=" * 60)

    return "\n".join(output)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Get context briefing")
    parser.add_argument("--full", action="store_true", help="Include recent activity")
    args = parser.parse_args()

    print(generate_briefing(full=args.full))
