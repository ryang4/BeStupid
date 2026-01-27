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

    # Deduplicate todos while preserving order
    # Normalize by extracting task text (remove "- [ ] " or "- [x] " prefix)
    def normalize_todo(todo):
        """Extract task text from todo for comparison."""
        text = todo.strip()
        if text.startswith("- [ ] "):
            text = text[6:]
        elif text.startswith("- [x] "):
            text = text[6:]
        return text.lower().strip()

    seen = set()
    combined_todos = []

    # Add in priority order: Top 3 first, then incomplete, then AI
    for todo in yesterday_top_3 + yesterday_incomplete + ai_todos:
        normalized = normalize_todo(todo)
        if normalized and normalized not in seen:
            seen.add(normalized)
            combined_todos.append(todo)

    print(f"   Deduplication: {len(yesterday_top_3) + len(yesterday_incomplete) + len(ai_todos)} -> {len(combined_todos)} todos")

    # 8. Build markdown using Jinja2 template
    content = render_daily_log(
        date_str=date_str,
        workout_type=ai_response.get('workout_type', 'recovery'),
        planned_workout=ai_response.get('planned_workout', 'No workout scheduled'),
        briefing=ai_response.get('briefing', {'focus': 'Execute protocol', 'tips': [], 'warnings': []}),
        todos=combined_todos,
        include_strength_log=ai_response.get('include_strength_log', False),
        strength_exercises=ai_response.get('strength_exercises', []),
        cardio_activities=ai_response.get('cardio_activities', []),
        habits=habits,
    )

    # 9. Write file
    with open(file_path, "w", encoding='utf-8') as f:
        f.write(content)

    # 10. Print summary
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
    print(f"   - Todos: {len(combined_todos)} items ({len(yesterday_incomplete)} rollover, {len(yesterday_top_3)} from Top 3, {len(ai_todos)} AI-generated)")
    print(f"   - Sections: {'Strength ' if include_strength else ''}{', '.join(cardio) if cardio else 'None'}")


if __name__ == "__main__":
    create_daily_log()
