"""
Daily Log Scheduler - AI-Powered Daily Planning

Generates today's log with:
- Protocol baseline workout (from weekly protocol)
- AI daily briefing (aggressive adjustments based on last 3 days)
- Todos (carryovers + new suggestions)

Uses Ollama (qwen) to read last 3 days and provide context-aware guidance.
"""

import os
import re
import sys
import frontmatter
from datetime import datetime, timedelta

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from llm_client import generate_daily_briefing, estimate_macros
from template_renderer import render_daily_log

# CONFIGURATION
# Use absolute paths based on project root (parent of scripts/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT_DIR = os.path.join(PROJECT_ROOT, "content/logs")
PROTOCOL_DIR = os.path.join(PROJECT_ROOT, "content/config")
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "templates")
RYAN_CONFIG = os.path.join(PROJECT_ROOT, "content/config/ryan.md")


def get_weekly_protocol():
    """
    Finds and returns the active Weekly Protocol content.

    Searches for protocol file using Monday's date of current week.
    Format: protocol_YYYY-MM-DD.md (where date is Monday)
    Falls back to old format (protocol_YYYY-WXX.md) during transition.

    Returns:
        str: Full protocol content (empty string if not found)
    """
    today = datetime.now()
    # Find Monday of current week (weekday 0 = Monday)
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    monday_str = monday.strftime("%Y-%m-%d")

    # Try new date-based format first
    protocol_file = f"protocol_{monday_str}.md"
    protocol_path = os.path.join(PROTOCOL_DIR, protocol_file)

    if os.path.exists(protocol_path):
        try:
            with open(protocol_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Error reading protocol: {e}")

    # Fallback to old week-number format during transition
    year, week, _ = today.isocalendar()
    old_protocol_file = f"protocol_{year}-W{week:02d}.md"
    old_protocol_path = os.path.join(PROTOCOL_DIR, old_protocol_file)

    if os.path.exists(old_protocol_path):
        print(f"Note: Using legacy protocol format {old_protocol_file}")
        try:
            with open(old_protocol_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Error reading protocol: {e}")

    return ""


def read_last_n_days(n=3):
    """
    Read last N days of daily logs for AI context.

    Returns:
        list: List of dicts with log data
    """
    logs = []
    today = datetime.now()

    for i in range(n, 0, -1):  # 3, 2, 1 (yesterday is most recent)
        past_date = today - timedelta(days=i)
        date_str = past_date.strftime("%Y-%m-%d")
        # Flat file path (not page bundle)
        log_path = os.path.join(VAULT_DIR, f"{date_str}.md")

        if os.path.exists(log_path):
            try:
                post = frontmatter.load(log_path)

                # Extract todos if they exist
                todos = []
                if 'todos' in post.metadata:
                    todos = post.metadata['todos']
                    if isinstance(todos, str):
                        todos = todos.strip().split('\n')
                    elif isinstance(todos, list):
                        todos = [str(t) for t in todos]

                log_data = {
                    "date": date_str,
                    "content": post.content,
                    "stats": {
                        "compliance": post.metadata.get('Compliance', 0),
                        "sleep_hours": post.metadata.get('Sleep Hours', 0),
                        "weight": post.metadata.get('Weight (lbs)', 0),
                    },
                    "todos": todos,
                    "narrative": post.content
                }
                logs.append(log_data)
            except Exception as e:
                print(f"⚠️  Warning: Could not read {log_path}: {e}")

    return logs


def get_yesterday_incomplete_todos():
    """
    Extract incomplete todos from yesterday's "Today's Todos" section.

    Finds all unchecked items (- [ ]) and returns them for rollover.

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

        # Find the "## Today's Todos" section
        if "## Today's Todos" not in content:
            print(f"   No 'Today's Todos' section in yesterday's log")
            return []

        # Get text after the header
        todos_start = content.index("## Today's Todos") + len("## Today's Todos")
        remaining = content[todos_start:]

        # Find the next section header (or end of file)
        next_section = remaining.find("\n## ")
        if next_section != -1:
            todos_text = remaining[:next_section].strip()
        else:
            todos_text = remaining.strip()

        # Parse incomplete todos (- [ ] items)
        incomplete_todos = []
        for line in todos_text.split('\n'):
            line = line.strip()
            # Match unchecked todo items: - [ ] Task
            if line.startswith("- [ ]"):
                incomplete_todos.append(line)

        if incomplete_todos:
            print(f"   Found {len(incomplete_todos)} incomplete todos from yesterday")
        else:
            print(f"   All todos from yesterday were completed!")

        return incomplete_todos

    except Exception as e:
        print(f"⚠️  Error extracting incomplete todos: {e}")
        return []


def get_yesterday_top_3():
    """
    Extract 'Top 3 for Tomorrow' items from yesterday's log.

    Parses the numbered list (1. 2. 3.) from the "## Top 3 for Tomorrow" section
    and converts them to checkbox format for today's todos.

    Returns:
        list: List of todo strings in "- [ ] Task" format, or empty list if none found
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

        # Find the "## Top 3 for Tomorrow" section
        if "## Top 3 for Tomorrow" not in content:
            print(f"   No 'Top 3 for Tomorrow' section in yesterday's log")
            return []

        # Get text after the header
        top3_start = content.index("## Top 3 for Tomorrow") + len("## Top 3 for Tomorrow")
        remaining = content[top3_start:]

        # Find the next section header (or end of file)
        next_section = remaining.find("\n## ")
        if next_section != -1:
            top3_text = remaining[:next_section].strip()
        else:
            top3_text = remaining.strip()

        # Parse numbered items (1. 2. 3.)
        todos = []
        for line in top3_text.split('\n'):
            # Match lines starting with "1.", "2.", "3." etc.
            match = re.match(r'^\d+\.\s+(.+)$', line.strip())
            if match:
                task = match.group(1).strip()
                if task:  # Only add non-empty tasks
                    todos.append(f"- [ ] {task}")

        if todos:
            print(f"   Found {len(todos)} items from yesterday's Top 3")
        else:
            print(f"   Top 3 section exists but no items found")

        return todos

    except Exception as e:
        print(f"⚠️  Error extracting Top 3: {e}")
        return []


def get_yesterday_macros():
    """
    Read yesterday's log and estimate macros from the Fuel Log section.

    Returns:
        dict with keys: calories, protein_g, carbs_g, fat_g
        Returns None if no fuel log found or estimation fails
    """
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    log_path = os.path.join(VAULT_DIR, f"{date_str}.md")

    if not os.path.exists(log_path):
        print(f"   No log found for yesterday ({date_str})")
        return None

    try:
        post = frontmatter.load(log_path)
        content = post.content

        # Extract Fuel Log section
        if "## Fuel Log" not in content:
            print(f"   No Fuel Log section in yesterday's log")
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

        # Skip if it's just the placeholder text
        if fuel_text.startswith("*Describe your food"):
            print(f"   Fuel Log not filled in for yesterday")
            return None

        if len(fuel_text) < 10:
            print(f"   Fuel Log too short to analyze")
            return None

        print(f"Estimating macros for yesterday ({date_str})...")
        return estimate_macros(fuel_text)

    except Exception as e:
        print(f"⚠️  Error reading yesterday's log: {e}")
        return None


def load_habits_config():
    """
    Load habit definitions from the habits config file.

    Returns:
        list: List of habit dicts with id and name, or empty list if not found
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
        print(f"⚠️  Error loading habits config: {e}")
        return []


def create_daily_log():
    """
    Generate today's daily log with AI-powered briefing and dynamic sections.
    """
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    day_name = today.strftime("%A")

    # Flat file path (not page bundle)
    file_path = os.path.join(VAULT_DIR, f"{date_str}.md")

    # Check if log already exists
    if os.path.exists(file_path):
        print(f"Log already exists for {date_str}")
        return

    print(f"Generating log for {date_str} ({day_name})...")

    # 0. Extract and save yesterday's metrics (non-blocking)
    print("Extracting yesterday's metrics...")
    try:
        from metrics_extractor import extract_and_save_yesterday
        metrics = extract_and_save_yesterday()
        if metrics:
            print(f"   Saved metrics for {metrics['date']}")
        else:
            print("   No metrics extracted (missing data or first day)")
    except Exception as e:
        print(f"   Warning: Metrics extraction failed: {e}")
        # Continue - never block log generation

    # 1. Get yesterday's macro estimates
    print("Checking yesterday's fuel log...")
    yesterday_macros = get_yesterday_macros()
    if yesterday_macros:
        print(f"   Estimated: {yesterday_macros['calories']} cal, {yesterday_macros['protein_g']}g protein")

    # 1b. Get yesterday's incomplete todos (rollover)
    print("Checking yesterday's incomplete todos...")
    yesterday_incomplete = get_yesterday_incomplete_todos()

    # 1c. Get yesterday's Top 3 for Tomorrow
    print("Checking yesterday's Top 3 for Tomorrow...")
    yesterday_top_3 = get_yesterday_top_3()

    # 1c. Load habits config
    print("Loading habits config...")
    habits = load_habits_config()

    # 2. Get full weekly protocol
    print("Reading weekly protocol...")
    full_protocol = get_weekly_protocol()

    # 2. Read last 3 days for AI context
    print("Reading last 3 days of logs...")
    last_3_days = read_last_n_days(3)
    print(f"   Found {len(last_3_days)} recent logs")

    # 3. Default fallback response
    ai_response = {
        "workout_type": "recovery",
        "planned_workout": "No protocol found - please create weekly protocol first.",
        "briefing": {
            "focus": "Create your weekly protocol to start tracking",
            "tips": ["Set up your weekly training schedule", "Log all stats and reflections daily"],
            "warnings": []
        },
        "todos": ["- [ ] Create weekly protocol", "- [ ] Log all stats and narrative"],
        "include_strength_log": False,
        "cardio_activities": []
    }

    if full_protocol:
        print("Generating AI daily briefing...")
        print("   (This may take 10-30 seconds...)")

        try:
            # Read Ryan's goals
            with open(RYAN_CONFIG, 'r', encoding='utf-8') as f:
                goals = f.read()

            ai_response = generate_daily_briefing(goals, full_protocol, last_3_days, day_name)
            print("   AI briefing generated")

        except RuntimeError as e:
            print(f"\nWarning: {e}")
            print("   Using fallback briefing")
        except Exception as e:
            print(f"\nWarning: Error generating AI briefing: {e}")
            print("   Using fallback briefing")

    # 4. Combine todos: incomplete rollover + Top 3 + AI-generated
    ai_todos = ai_response.get('todos', ['- [ ] Review today\'s protocol'])
    combined_todos = yesterday_incomplete + yesterday_top_3 + ai_todos

    # 5. Build markdown using Jinja2 template
    content = render_daily_log(
        date_str=date_str,
        workout_type=ai_response.get('workout_type', 'recovery'),
        planned_workout=ai_response.get('planned_workout', 'No workout scheduled'),
        briefing=ai_response.get('briefing', 'Execute protocol as planned.'),
        todos=combined_todos,
        include_strength_log=ai_response.get('include_strength_log', False),
        strength_exercises=ai_response.get('strength_exercises', []),
        cardio_activities=ai_response.get('cardio_activities', []),
        yesterday_macros=yesterday_macros,
        habits=habits,
    )

    # 6. Write file (no folder creation needed)
    with open(file_path, "w", encoding='utf-8') as f:
        f.write(content)

    # 7. Print summary
    workout_type = ai_response.get('workout_type', 'recovery')
    planned_workout = ai_response.get('planned_workout', '')
    briefing = ai_response.get('briefing', '')
    include_strength = ai_response.get('include_strength_log', False)
    cardio = ai_response.get('cardio_activities', [])

    print(f"\nGenerated log: {file_path}")
    print("\nSummary:")
    print(f"   - Type: {workout_type}")
    print(f"   - Workout: {planned_workout[:50]}...")
    print(f"   - Briefing: {briefing[:50]}...")
    print(f"   - Todos: {len(combined_todos)} items ({len(yesterday_incomplete)} rollover, {len(yesterday_top_3)} from Top 3, {len(ai_todos)} AI-generated)")
    print(f"   - Sections: {'Strength ' if include_strength else ''}{', '.join(cardio) if cardio else 'None'}")


if __name__ == "__main__":
    create_daily_log()
