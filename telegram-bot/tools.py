"""
Tool implementations for BeStupid Telegram bot.
Each tool maps to a BeStupid skill capability.
"""

import os
import re
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from glob import glob

# Add scripts to path
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

REPO_ROOT = PROJECT_ROOT
PRIVATE_DIR = Path.home() / ".bestupid-private"

# Tool definitions for Claude
TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from the BeStupid repo (logs, protocols, config, projects)",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from repo root, e.g. 'content/logs/2026-01-23.md'"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write or update a file in the BeStupid repo",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from repo root"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "update_metric",
        "description": "Update a metric in today's log (weight, sleep, mood, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": ["Weight", "Sleep", "Sleep_Quality", "Mood_AM", "Mood_PM"],
                    "description": "The metric field to update"
                },
                "value": {"type": "string", "description": "The value to set"}
            },
            "required": ["field", "value"]
        }
    },
    {
        "name": "run_daily_planner",
        "description": "Generate today's daily log with AI briefing and workout schedule",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "run_weekly_planner",
        "description": "Generate next week's training and work protocol",
        "input_schema": {
            "type": "object",
            "properties": {
                "this_week": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, regenerate current week's protocol instead of next week's"
                }
            }
        }
    },
    {
        "name": "get_brain_status",
        "description": "Get current status: priorities, health check, today's workout, blockers",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "capture_to_inbox",
        "description": "Capture an idea or task to the inbox for later processing",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to capture"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "search_logs",
        "description": "Search through log files for a query term",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "days": {
                    "type": "integer",
                    "default": 30,
                    "description": "Number of days to search back"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from repo root, e.g. 'content/logs'"
                },
                "pattern": {
                    "type": "string",
                    "default": "*",
                    "description": "Glob pattern to filter files"
                }
            },
            "required": ["path"]
        }
    }
]


async def execute_tool(name: str, inputs: dict) -> str:
    """Execute a tool and return result string."""

    if name == "read_file":
        return read_file(inputs["path"])

    elif name == "write_file":
        return write_file(inputs["path"], inputs["content"])

    elif name == "update_metric":
        return update_metric_in_log(inputs["field"], inputs["value"])

    elif name == "run_daily_planner":
        return run_daily_planner()

    elif name == "run_weekly_planner":
        this_week = inputs.get("this_week", False)
        return run_weekly_planner(this_week=this_week)

    elif name == "get_brain_status":
        return get_brain_status()

    elif name == "capture_to_inbox":
        return capture_to_inbox(inputs["text"])

    elif name == "search_logs":
        return search_logs(inputs["query"], inputs.get("days", 30))

    elif name == "list_files":
        return list_files(inputs["path"], inputs.get("pattern", "*"))

    return f"Unknown tool: {name}"


def read_file(path: str) -> str:
    """Read a file from the repo."""
    # Handle absolute paths to private dir
    if path.startswith("~"):
        full_path = Path(path).expanduser()
    else:
        full_path = REPO_ROOT / path

    if full_path.exists():
        return full_path.read_text()
    return f"File not found: {path}"


def write_file(path: str, content: str) -> str:
    """Write a file to the repo."""
    full_path = REPO_ROOT / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    return f"Wrote {len(content)} bytes to {path}"


def list_files(path: str, pattern: str = "*") -> str:
    """List files in a directory."""
    full_path = REPO_ROOT / path
    if not full_path.exists():
        return f"Directory not found: {path}"

    files = sorted(full_path.glob(pattern))
    return "\n".join(f.name for f in files[-20:])  # Last 20 files


def update_metric_in_log(field: str, value: str) -> str:
    """Update a metric field in today's log."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = REPO_ROOT / "content" / "logs" / f"{today}.md"

    if not log_path.exists():
        return f"Today's log doesn't exist ({today}.md). Run /planday first."

    content = log_path.read_text()
    pattern = rf"^{field}::.*$"
    replacement = f"{field}:: {value}"

    new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)

    if count > 0:
        log_path.write_text(new_content)
        return f"Updated {field}:: {value}"
    else:
        # Field not found, try to add it to Quick Log section
        if "## Quick Log" in content:
            new_content = content.replace(
                "## Quick Log",
                f"## Quick Log\n{field}:: {value}"
            )
            log_path.write_text(new_content)
            return f"Added {field}:: {value} to Quick Log section"
        return f"Field '{field}::' not found in today's log."


def run_daily_planner() -> str:
    """Run the daily planner script."""
    try:
        # Change to project root for script to work
        original_cwd = os.getcwd()
        os.chdir(str(REPO_ROOT))

        from daily_planner import create_daily_log
        create_daily_log()

        os.chdir(original_cwd)

        today = datetime.now().strftime("%Y-%m-%d")
        return f"Daily log created: content/logs/{today}.md"
    except Exception as e:
        return f"Error creating daily log: {e}"


def run_weekly_planner(this_week: bool = False) -> str:
    """Run the weekly planner script."""
    try:
        original_cwd = os.getcwd()
        os.chdir(str(REPO_ROOT))

        from weekly_planner import create_weekly_protocol
        result = create_weekly_protocol(this_week=this_week)

        os.chdir(original_cwd)

        return f"Weekly protocol created: {result}"
    except ImportError:
        # Fallback to subprocess if module doesn't have the function
        import subprocess
        cmd = ["python", str(SCRIPTS_DIR / "weekly_planner.py")]
        if this_week:
            cmd.append("--this-week")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
        if result.returncode == 0:
            return f"Weekly protocol created.\n{result.stdout}"
        return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error creating weekly protocol: {e}"


def get_brain_status() -> str:
    """Build brain status from multiple sources."""
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    day_name = today.strftime("%A")

    output = []
    output.append(f"## Brain Status - {day_name}, {today_str}\n")

    # 1. Today's log status
    log_path = REPO_ROOT / "content" / "logs" / f"{today_str}.md"
    if log_path.exists():
        log_content = log_path.read_text()

        # Extract incomplete todos
        todos = []
        if "## Today's Todos" in log_content:
            todos_section = log_content.split("## Today's Todos")[1]
            if "\n## " in todos_section:
                todos_section = todos_section.split("\n## ")[0]
            for line in todos_section.split("\n"):
                if line.strip().startswith("- [ ]"):
                    todos.append(line.strip())

        if todos:
            output.append("### Incomplete Todos")
            for todo in todos[:10]:
                output.append(todo)
            output.append("")

        # Extract metrics
        metrics = {}
        for field in ["Weight", "Sleep", "Sleep_Quality", "Mood_AM", "Mood_PM"]:
            match = re.search(rf"^{field}::\s*(.*)$", log_content, re.MULTILINE)
            if match and match.group(1).strip():
                metrics[field] = match.group(1).strip()

        if metrics:
            output.append("### Today's Metrics")
            for k, v in metrics.items():
                output.append(f"- {k}: {v}")
            output.append("")
    else:
        output.append("*Today's log doesn't exist yet. Run /planday to create it.*\n")

    # 2. 7-day metrics analysis
    try:
        from metrics_analyzer import generate_llm_summary
        summary = generate_llm_summary(full_context=True)

        output.append("### 7-Day Averages")
        avgs = summary.get("rolling_7day_averages", {})
        if avgs.get("sleep_hours"):
            output.append(f"- Sleep: {avgs['sleep_hours']} hrs")
        if avgs.get("mood_morning"):
            output.append(f"- Morning Mood: {avgs['mood_morning']}/10")
        if avgs.get("todo_completion_rate"):
            output.append(f"- Todo Completion: {int(avgs['todo_completion_rate'] * 100)}%")
        if avgs.get("weight_lbs"):
            output.append(f"- Weight: {avgs['weight_lbs']} lbs")
        output.append("")

        # Warnings
        warnings = summary.get("recommendations", {}).get("warnings", [])
        if warnings:
            output.append("### Warnings")
            for w in warnings:
                output.append(f"- {w}")
            output.append("")

        # Streaks
        streaks = summary.get("streaks", {})
        if streaks.get("current_streak"):
            status = "positive" if streaks["current_streak"] > 0 else "needs attention"
            output.append(f"### Streak: {abs(streaks['current_streak'])} days ({status})\n")

    except Exception as e:
        output.append(f"*Metrics analysis unavailable: {e}*\n")

    # 3. Active protocol / today's workout
    try:
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        monday_str = monday.strftime("%Y-%m-%d")
        protocol_path = REPO_ROOT / "content" / "config" / f"protocol_{monday_str}.md"

        if protocol_path.exists():
            protocol_content = protocol_path.read_text()
            output.append("### Today's Planned Workout")
            # Extract today's schedule from protocol
            if "## Weekly Schedule" in protocol_content:
                schedule_section = protocol_content.split("## Weekly Schedule")[1]
                if "\n## " in schedule_section:
                    schedule_section = schedule_section.split("\n## ")[0]
                for line in schedule_section.split("\n"):
                    if day_name in line:
                        output.append(line)
            output.append("")
        else:
            output.append("*No active protocol found for this week.*\n")
    except Exception as e:
        output.append(f"*Protocol unavailable: {e}*\n")

    # 4. Inbox count
    inbox_path = PRIVATE_DIR / "inbox.md"
    if inbox_path.exists():
        inbox_content = inbox_path.read_text()
        inbox_items = len([l for l in inbox_content.split("\n") if l.strip().startswith("- [")])
        if inbox_items > 0:
            output.append(f"### Inbox: {inbox_items} pending items\n")

    return "\n".join(output)


def capture_to_inbox(text: str) -> str:
    """Append to inbox file."""
    inbox_path = PRIVATE_DIR / "inbox.md"
    inbox_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- [{timestamp}] {text}\n"

    # Create file with header if it doesn't exist
    if not inbox_path.exists():
        inbox_path.write_text("# Inbox\n\n<!-- New items -->\n")

    with open(inbox_path, "a") as f:
        f.write(entry)

    return f"Captured: {text}"


def search_logs(query: str, days: int = 30) -> str:
    """Search through recent logs."""
    logs_dir = REPO_ROOT / "content" / "logs"
    results = []

    cutoff = datetime.now() - timedelta(days=days)

    for log_file in sorted(logs_dir.glob("*.md"), reverse=True):
        try:
            date_str = log_file.stem
            log_date = datetime.strptime(date_str, "%Y-%m-%d")
            if log_date < cutoff:
                break

            content = log_file.read_text()
            for i, line in enumerate(content.split("\n")):
                if query.lower() in line.lower():
                    results.append(f"**{date_str}**: {line.strip()}")
                    if len(results) >= 10:
                        break
            if len(results) >= 10:
                break
        except ValueError:
            continue

    if results:
        return f"Found {len(results)} matches:\n" + "\n".join(results)
    return f"No matches for '{query}' in last {days} days."
