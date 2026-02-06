"""
Daily Log Scheduler - AI-Powered Daily Planning

Generates today's log with:
- Protocol baseline workout (from weekly protocol)
- AI daily briefing (based on 7-day metrics analysis)
- Adaptive todos (based on completion rate patterns)

Uses structured metrics from metrics_analyzer.py to provide context-aware guidance.
"""

import os
import re
import sys
import frontmatter
from datetime import datetime, timedelta
from typing import Optional

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from llm_client import generate_daily_briefing
from template_renderer import render_daily_log
from metrics_analyzer import generate_llm_summary, get_recent_entries_summary

# Configuration
VAULT_DIR = "content/logs"
PROTOCOL_DIR = "content/config"
TEMPLATE_DIR = "templates"
RYAN_CONFIG = "content/config/ryan.md"
WORKOUT_KEYWORDS = ("workout", "swim", "bike", "run", "strength", "brick", "protocol")
DEFAULT_MUST_WIN = [
    "Ship one high-leverage startup task before noon.",
    "Complete today's workout or recovery protocol.",
    "Close the loop: fill Quick Log + Top 3 for tomorrow.",
]
DEFAULT_CAN_DO = [
    "Process inbox captures and defer low-leverage work.",
    "Send one high-value follow-up message.",
]


def get_weekly_protocol():
    """
    Find and return the active Weekly Protocol content.

    Searches for protocol file using Monday's date of current week.
    Format: protocol_YYYY-MM-DD.md (where date is Monday)

    Returns:
        str: Full protocol content (empty string if not found)
    """
    today = datetime.now()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    monday_str = monday.strftime("%Y-%m-%d")

    protocol_file = f"protocol_{monday_str}.md"
    protocol_path = os.path.join(PROTOCOL_DIR, protocol_file)
    print(f"   Looking for: {protocol_path}")

    if os.path.exists(protocol_path):
        try:
            with open(protocol_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Error reading protocol: {e}")

    return ""


def get_yesterday_incomplete_todos():
    """
    Extract incomplete todos from yesterday's log.

    Finds all unchecked items (- [ ]) in Today's Todos section.

    Returns:
        list: List of incomplete todo strings in "- [ ] Task" format
    """
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    log_path = os.path.join(VAULT_DIR, f"{date_str}.md")

    if not os.path.exists(log_path):
        print(f"   No log found for yesterday ({date_str})")
        return []

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if "## Today's Todos" not in content:
            print(f"   No 'Today's Todos' section in yesterday's log")
            return []

        todos_start = content.index("## Today's Todos") + len("## Today's Todos")
        remaining = content[todos_start:]

        next_section = remaining.find("\n## ")
        todos_text = remaining[:next_section].strip() if next_section != -1 else remaining.strip()

        incomplete_todos = []
        for line in todos_text.split('\n'):
            line = line.strip()
            if line.startswith("- [ ]"):
                incomplete_todos.append(line)

        if incomplete_todos:
            print(f"   Found {len(incomplete_todos)} incomplete todos from yesterday")
        else:
            print(f"   All todos from yesterday were completed!")

        return incomplete_todos

    except Exception as e:
        print(f"Warning: Error extracting incomplete todos: {e}")
        return []


def get_yesterday_top_3():
    """
    Extract 'Top 3 for Tomorrow' items from yesterday's log.

    Parses numbered list and converts to checkbox format.

    Returns:
        list: List of todo strings in "- [ ] Task" format
    """
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    log_path = os.path.join(VAULT_DIR, f"{date_str}.md")

    if not os.path.exists(log_path):
        print(f"   No log found for yesterday ({date_str})")
        return []

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if "## Top 3 for Tomorrow" not in content:
            print(f"   No 'Top 3 for Tomorrow' section in yesterday's log")
            return []

        top3_start = content.index("## Top 3 for Tomorrow") + len("## Top 3 for Tomorrow")
        remaining = content[top3_start:]

        next_section = remaining.find("\n## ")
        top3_text = remaining[:next_section].strip() if next_section != -1 else remaining.strip()

        todos = []
        for line in top3_text.split('\n'):
            match = re.match(r'^\d+\.\s+(.+)$', line.strip())
            if match:
                task = match.group(1).strip()
                if task:
                    todos.append(f"- [ ] {task}")

        if todos:
            print(f"   Found {len(todos)} items from yesterday's Top 3")
        else:
            print(f"   Top 3 section exists but no items found")

        return todos

    except Exception as e:
        print(f"Warning: Error extracting Top 3: {e}")
        return []


def load_habits_config():
    """
    Load habit definitions from the habits config file.

    Returns:
        list: List of habit dicts with id and name
    """
    habits_path = os.path.join(PROTOCOL_DIR, "habits.md")

    if not os.path.exists(habits_path):
        print("   No habits.md config found")
        return []

    try:
        post = frontmatter.load(habits_path)
        habits = post.metadata.get('habits', [])
        print(f"   Loaded {len(habits)} habits from config")
        return habits
    except Exception as e:
        print(f"Warning: Error loading habits config: {e}")
        return []


def extract_yesterday_metrics():
    """
    Extract and save yesterday's metrics (non-blocking).

    Returns:
        dict: Extracted metrics, or None
    """
    try:
        from metrics_extractor import extract_and_save_yesterday
        metrics = extract_and_save_yesterday()
        if metrics:
            print(f"   Saved metrics for {metrics['date']}")
        else:
            print("   No metrics extracted (missing data or first day)")
        return metrics
    except Exception as e:
        print(f"   Warning: Metrics extraction failed: {e}")
        return None


def normalize_todo(todo: str) -> str:
    """Extract task text from checkbox format for stable comparisons."""
    text = todo.strip()
    if text.startswith("- [ ] "):
        text = text[6:]
    elif text.startswith("- [x] "):
        text = text[6:]
    elif text.startswith("- "):
        text = text[2:]
    return text.strip()


def as_checkbox(todo: str) -> str:
    """Ensure a todo is in markdown checkbox format."""
    cleaned = normalize_todo(todo)
    return f"- [ ] {cleaned}" if cleaned else ""


def dedupe_todos(todos: list[str]) -> list[str]:
    """Deduplicate todos while preserving original order."""
    seen = set()
    deduped = []

    for todo in todos:
        normalized = normalize_todo(todo).lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalize_todo(todo))

    return deduped


def get_recovery_score() -> Optional[int]:
    """Get latest Garmin recovery score if available."""
    try:
        from garmin_sync import get_latest_recovery
        recovery = get_latest_recovery() or {}
        score = recovery.get("recovery", {}).get("score")
        if isinstance(score, (int, float)):
            return int(score)
    except Exception:
        pass
    return None


def is_workout_todo(todo_text: str) -> bool:
    """Check if a todo is workout-related."""
    lowered = todo_text.lower()
    return any(keyword in lowered for keyword in WORKOUT_KEYWORDS)


def build_command_engine(backlog_todos: list[str], metrics_summary: dict) -> dict:
    """
    Build a hard daily execution plan:
    - Must Win 3 (non-negotiable)
    - Can Do 2 (optional)
    - Not Today (deferred)

    Uses 7-day completion, 7-day sleep, and recovery score (if available)
    to adjust workload aggressiveness.
    """
    rolling = metrics_summary.get("rolling_7day_averages", {})
    recommendations = metrics_summary.get("recommendations", {})

    completion_rate = rolling.get("todo_completion_rate")
    sleep_hours = rolling.get("sleep_hours")
    recovery_score = get_recovery_score()

    severe_flags = []
    soft_flags = []

    if completion_rate is not None:
        if completion_rate < 0.50:
            severe_flags.append(f"7-day completion at {completion_rate * 100:.0f}% (<50%)")
        elif completion_rate < 0.70:
            soft_flags.append(f"7-day completion at {completion_rate * 100:.0f}% (<70%)")

    if sleep_hours is not None:
        if sleep_hours < 6.5:
            severe_flags.append(f"7-day sleep avg {sleep_hours:.1f}h (<6.5h)")
        elif sleep_hours < 7.0:
            soft_flags.append(f"7-day sleep avg {sleep_hours:.1f}h (<7h)")

    if recovery_score is not None:
        if recovery_score < 50:
            severe_flags.append(f"Recovery score {recovery_score}/100 (<50)")
        elif recovery_score < 65:
            soft_flags.append(f"Recovery score {recovery_score}/100 (<65)")

    if recommendations.get("max_todos", 3) <= 2:
        soft_flags.append("Recent completion trend suggests smaller scope")

    capacity_score = 5
    if completion_rate is not None:
        if completion_rate < 0.50:
            capacity_score -= 2
        elif completion_rate < 0.70:
            capacity_score -= 1
    if sleep_hours is not None:
        if sleep_hours < 6.5:
            capacity_score -= 2
        elif sleep_hours < 7.0:
            capacity_score -= 1
    if recovery_score is not None:
        if recovery_score < 50:
            capacity_score -= 2
        elif recovery_score < 65:
            capacity_score -= 1
    capacity_score = max(2, min(5, capacity_score))

    if severe_flags:
        workload_tier = "recovery-protect"
    elif soft_flags:
        workload_tier = "focused"
    else:
        workload_tier = "attack"

    backlog = dedupe_todos(backlog_todos)
    must_win = []
    can_do = []
    not_today = []
    remaining = list(backlog)

    workout_idx = next((i for i, task in enumerate(remaining) if is_workout_todo(task)), None)
    if workout_idx is not None:
        must_win.append(remaining.pop(workout_idx))

    while remaining and len(must_win) < 3:
        must_win.append(remaining.pop(0))

    while remaining and len(can_do) < 2:
        can_do.append(remaining.pop(0))

    not_today.extend(remaining)

    seen = {normalize_todo(task).lower() for task in must_win + can_do}

    for default in DEFAULT_MUST_WIN:
        if len(must_win) >= 3:
            break
        normalized = normalize_todo(default).lower()
        if normalized in seen:
            continue
        must_win.append(default)
        seen.add(normalized)

    for default in DEFAULT_CAN_DO:
        if len(can_do) >= 2:
            break
        normalized = normalize_todo(default).lower()
        if normalized in seen:
            continue
        can_do.append(default)
        seen.add(normalized)

    guardrail = "Do not add new tasks until Must Win 3 are done."
    guardrail_norm = normalize_todo(guardrail).lower()

    if workload_tier == "recovery-protect":
        if not any(normalize_todo(task).lower() == guardrail_norm for task in not_today):
            not_today.insert(0, guardrail)
    elif not not_today:
        not_today.append("Keep intake closed until Must Win 3 are complete.")

    signals = severe_flags + soft_flags
    if not signals:
        signals = ["All readiness signals green. Push quality, not task count."]

    must_win = must_win[:3]
    can_do = can_do[:2]

    return {
        "workload_tier": workload_tier,
        "capacity_score": capacity_score,
        "signals": signals[:3],
        "must_win": must_win,
        "can_do": can_do,
        "not_today": not_today[:6],
        "execution_todos": [as_checkbox(task) for task in must_win + can_do if as_checkbox(task)],
    }


def create_daily_log():
    """
    Generate today's daily log with AI-powered briefing and metrics-aware context.
    """
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    day_name = today.strftime("%A")

    file_path = os.path.join(VAULT_DIR, f"{date_str}.md")

    if os.path.exists(file_path):
        print(f"Log already exists for {date_str}")
        return

    print(f"Generating log for {date_str} ({day_name})...")

    # 1. Extract yesterday's metrics (non-blocking)
    print("Extracting yesterday's metrics...")
    extract_yesterday_metrics()

    # 2. Get rollover items
    print("Checking yesterday's incomplete todos...")
    yesterday_incomplete = get_yesterday_incomplete_todos()

    print("Checking yesterday's Top 3 for Tomorrow...")
    yesterday_top_3 = get_yesterday_top_3()

    # 3. Load habits config
    print("Loading habits config...")
    habits = load_habits_config()

    # 4. Get weekly protocol
    print("Reading weekly protocol...")
    full_protocol = get_weekly_protocol()

    # 5. Generate metrics analysis for LLM context
    print("Analyzing 7-day metrics trends...")
    metrics_summary = generate_llm_summary(full_context=True)
    recent_entries = get_recent_entries_summary(n_full=3, n_summary=4)

    print(f"   Metrics: {metrics_summary['days_analyzed']} days analyzed")
    if metrics_summary['recommendations']['warnings']:
        print(f"   Warnings: {len(metrics_summary['recommendations']['warnings'])}")
    print(f"   Recommended todos: {metrics_summary['recommendations']['max_todos']}")

    # 6. Default fallback response
    ai_response = {
        "workout_type": "recovery",
        "planned_workout": "No protocol found - please create weekly protocol first.",
        "briefing": {
            "focus": "Create your weekly protocol to start tracking",
            "tips": ["Set up your weekly training schedule", "Log all stats daily"],
            "warnings": []
        },
        "todos": ["- [ ] Create weekly protocol"],
        "include_strength_log": False,
        "cardio_activities": []
    }

    if full_protocol:
        print("Generating AI daily briefing...")
        print("   (This may take 10-30 seconds...)")

        try:
            with open(RYAN_CONFIG, 'r', encoding='utf-8') as f:
                goals = f.read()

            # Pass structured metrics to LLM
            ai_response = generate_daily_briefing(
                goals=goals,
                protocol=full_protocol,
                recent_entries=recent_entries,
                metrics_summary=metrics_summary,
                day_name=day_name
            )
            print("   AI briefing generated")

        except RuntimeError as e:
            print(f"\nWarning: {e}")
            print("   Using fallback briefing")
        except Exception as e:
            print(f"\nWarning: Error generating AI briefing: {e}")
            print("   Using fallback briefing")

    # 7. Combine todos: Top 3 from yesterday + incomplete rollover + AI-generated
    # Top 3 comes first (these are the priority tasks user planned)
    # Then incomplete todos that weren't finished
    # Then AI-generated todos (usually just "Perform today's workout")
    raw_ai_todos = ai_response.get('todos', ['- [ ] Review today\'s protocol'])

    # Filter AI todos: only keep the workout todo, remove spurious items
    # The LLM should only generate "Perform today's workout" but sometimes adds extras
    ai_todos = []
    for todo in raw_ai_todos:
        todo_lower = todo.lower()
        # Only keep workout-related todos from AI
        if 'workout' in todo_lower or 'protocol' in todo_lower:
            # Skip "create weekly protocol" - that's handled separately
            if 'create weekly protocol' not in todo_lower:
                ai_todos.append(todo)
                break  # Only keep one workout todo

    # Fallback if no valid AI todo found
    if not ai_todos and raw_ai_todos:
        ai_todos = ['- [ ] Perform today\'s workout']

    combined_todos = []
    seen = set()
    for todo in yesterday_top_3 + yesterday_incomplete + ai_todos:
        normalized = normalize_todo(todo).lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            combined_todos.append(as_checkbox(todo))

    print(f"   Deduplication: {len(yesterday_top_3) + len(yesterday_incomplete) + len(ai_todos)} -> {len(combined_todos)} todos")

    # 8. Build command engine execution plan
    command_engine = build_command_engine(combined_todos, metrics_summary)
    execution_todos = command_engine.get("execution_todos", [])
    print(
        f"   Command engine: {command_engine['workload_tier']} load | "
        f"Must Win {len(command_engine['must_win'])}, Can Do {len(command_engine['can_do'])}, "
        f"Deferred {len(command_engine['not_today'])}"
    )

    # 9. Build markdown using Jinja2 template
    content = render_daily_log(
        date_str=date_str,
        workout_type=ai_response.get('workout_type', 'recovery'),
        planned_workout=ai_response.get('planned_workout', 'No workout scheduled'),
        briefing=ai_response.get('briefing', {'focus': 'Execute protocol', 'tips': [], 'warnings': []}),
        todos=execution_todos,
        command_engine=command_engine,
        include_strength_log=ai_response.get('include_strength_log', False),
        strength_exercises=ai_response.get('strength_exercises', []),
        cardio_activities=ai_response.get('cardio_activities', []),
        habits=habits,
    )

    # 10. Write file
    with open(file_path, "w", encoding='utf-8') as f:
        f.write(content)

    # 11. Extract memory from yesterday's log (batch extraction)
    try:
        from memory import extract_and_persist
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_path = os.path.join(VAULT_DIR, f"{yesterday.strftime('%Y-%m-%d')}.md")
        if os.path.exists(yesterday_path):
            with open(yesterday_path, 'r', encoding='utf-8') as f:
                yesterday_content = f.read()
            print("Extracting memory from yesterday's log...")
            extracted = extract_and_persist(yesterday_content, agent="daily_planner")
            print(f"   Extracted {len(extracted)} facts into memory")
    except Exception as e:
        print(f"   Warning: Memory extraction failed: {e}")

    # 12. Print summary
    workout_type = ai_response.get('workout_type', 'recovery')
    planned_workout = ai_response.get('planned_workout', '')
    briefing = ai_response.get('briefing', {})
    include_strength = ai_response.get('include_strength_log', False)
    cardio = ai_response.get('cardio_activities', [])

    print(f"\nGenerated log: {file_path}")
    print("\nSummary:")
    print(f"   - Type: {workout_type}")
    print(f"   - Workout: {planned_workout[:50]}...")
    briefing_focus = briefing.get('focus', str(briefing)) if isinstance(briefing, dict) else str(briefing)
    print(f"   - Briefing: {briefing_focus[:50]}...")
    print(
        f"   - Backlog candidates: {len(combined_todos)} "
        f"({len(yesterday_incomplete)} rollover, {len(yesterday_top_3)} from Top 3, {len(ai_todos)} AI-generated)"
    )
    print(
        f"   - Execution list: {len(execution_todos)} "
        f"(Must Win {len(command_engine['must_win'])}, Can Do {len(command_engine['can_do'])})"
    )
    print(f"   - Deferred to Not Today: {len(command_engine['not_today'])}")
    print(f"   - Sections: {'Strength ' if include_strength else ''}{', '.join(cardio) if cardio else 'None'}")


if __name__ == "__main__":
    create_daily_log()
