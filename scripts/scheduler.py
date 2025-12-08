"""
Daily Log Scheduler - AI-Powered Daily Planning

Generates today's log with:
- Protocol baseline workout (from weekly protocol)
- AI daily briefing (aggressive adjustments based on last 3 days)
- Todos (carryovers + new suggestions)

Uses Ollama (qwen) to read last 3 days and provide context-aware guidance.
"""

import os
import sys
import frontmatter
from datetime import datetime, timedelta

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from ollama_client import generate_daily_briefing

# CONFIGURATION
VAULT_DIR = "content/logs"
PROTOCOL_DIR = "content/config"
TEMPLATE_DIR = "templates"
RYAN_CONFIG = "content/config/ryan.md"


def get_todays_protocol_mission():
    """
    Finds the active Weekly Protocol and extracts today's baseline workout.
    """
    today = datetime.now()
    year, week, _ = today.isocalendar()
    day_name = today.strftime("%A").lower()

    protocol_file = f"protocol_{year}-W{week:02d}.md"
    protocol_path = os.path.join(PROTOCOL_DIR, protocol_file)

    mission = {"type": "Rest", "desc": "No protocol found."}
    full_protocol = None

    if os.path.exists(protocol_path):
        try:
            with open(protocol_path, 'r', encoding='utf-8') as f:
                full_protocol = f.read()
                data = frontmatter.loads(full_protocol)

            schedule = data.get('schedule', {})
            daily_plan = schedule.get(day_name)

            if daily_plan:
                mission = daily_plan
        except Exception as e:
            print(f"⚠️  Error reading protocol: {e}")

    return mission, full_protocol


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
        log_path = os.path.join(VAULT_DIR, date_str, "index.md")

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


def create_daily_log():
    """
    Generate today's daily log with AI-powered briefing and todos.
    """
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    folder_path = os.path.join(VAULT_DIR, date_str)
    file_path = os.path.join(folder_path, "index.md")

    # Check if log already exists
    if os.path.exists(file_path):
        print(f"⏭️  Log already exists for {date_str}")
        return

    print(f"📅 Generating log for {date_str}...")

    # 1. Get protocol baseline mission
    print("📖 Reading weekly protocol...")
    mission, full_protocol = get_todays_protocol_mission()
    print(f"   ✓ Protocol mission: {mission.get('type')}")

    # 2. Read last 3 days for AI context
    print("📖 Reading last 3 days of logs...")
    last_3_days = read_last_n_days(3)
    print(f"   ✓ Found {len(last_3_days)} recent logs")

    # 3. Generate AI briefing and todos
    briefing = "First day of tracking - no historical context yet. Execute protocol as planned."
    todos_list = ["- [ ] Complete today's planned workout", "- [ ] Log all stats and narrative"]

    if full_protocol and (last_3_days or mission.get('desc') != "No protocol found."):
        print("🤖 Calling Ollama (qwen) for daily briefing...")
        print("   (This may take 10-30 seconds...)")

        try:
            # Read Ryan's goals
            with open(RYAN_CONFIG, 'r', encoding='utf-8') as f:
                goals = f.read()

            ai_response = generate_daily_briefing(goals, full_protocol, last_3_days)

            briefing = ai_response.get('briefing', briefing)
            todos_list = ai_response.get('todos', todos_list)

            print("   ✓ AI briefing generated")

        except ConnectionError as e:
            print(f"\n⚠️  {e}")
            print("   → Using fallback briefing (Ollama not available)")
        except Exception as e:
            print(f"\n⚠️  Error generating AI briefing: {e}")
            print("   → Using fallback briefing")

    # 4. Format todos as YAML list
    todos_yaml = "\n".join([f"  {todo}" for todo in todos_list])

    # 5. Load template and inject data
    with open(os.path.join(TEMPLATE_DIR, "daily_log.md"), "r", encoding='utf-8') as t:
        content = t.read()

    # Inject all placeholders
    content = content.replace("{{date:YYYY-MM-DD}}", date_str)
    content = content.replace("{{plan_desc}}", mission.get('desc', 'Active Recovery'))
    content = content.replace("{{daily_briefing}}", briefing)
    content = content.replace("{{todos}}", todos_yaml)

    # 6. Create folder and write file
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    with open(file_path, "w", encoding='utf-8') as f:
        f.write(content)

    print(f"\n✅ Generated log: {file_path}")
    print(f"\n📝 Summary:")
    print(f"   - Protocol: {mission.get('type')} - {mission.get('desc')}")
    print(f"   - AI Briefing: {briefing[:80]}...")
    print(f"   - Todos: {len(todos_list)} items")


if __name__ == "__main__":
    create_daily_log()
