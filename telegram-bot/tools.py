"""
Tool implementations for BeStupid Telegram bot.
Each tool maps to a BeStupid skill capability.
"""

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

REPO_ROOT = PROJECT_ROOT
PRIVATE_DIR = Path.home() / ".bestupid-private"

# --- Security: path restrictions ---

READABLE_PREFIXES = [
    REPO_ROOT / "content",
    REPO_ROOT / "memory",
    REPO_ROOT / "scripts",
    PRIVATE_DIR,
]

WRITABLE_PREFIXES = [
    REPO_ROOT / "content" / "logs",
    REPO_ROOT / "memory",
    PRIVATE_DIR,
]

BLOCKED_PATTERNS = [".env", ".git/", ".git\\", "__pycache__"]


def _is_path_blocked(path: Path) -> bool:
    s = str(path)
    return any(pat in s for pat in BLOCKED_PATTERNS)


def _check_readable(path: Path) -> str | None:
    """Return error string if path is not readable, else None."""
    resolved = path.resolve()
    if _is_path_blocked(resolved):
        return f"Access denied: {path}"
    for prefix in READABLE_PREFIXES:
        try:
            resolved.relative_to(prefix.resolve())
            return None
        except ValueError:
            continue
    return f"Access denied: {path} is not in an allowed read path"


def _check_writable(path: Path) -> str | None:
    """Return error string if path is not writable, else None."""
    resolved = path.resolve()
    if _is_path_blocked(resolved):
        return f"Access denied: {path}"
    for prefix in WRITABLE_PREFIXES:
        try:
            resolved.relative_to(prefix.resolve())
            return None
        except ValueError:
            continue
    return f"Access denied: {path} is not in an allowed write path"


# --- Cron security ---

ALLOWED_CRON_COMMANDS = {
    "morning_briefing": "cd /project && python telegram-bot/send_notification.py morning",
    "evening_reminder": "cd /project && python telegram-bot/send_notification.py evening",
    "daily_planner": "cd /project && python scripts/daily_planner.py",
    "auto_backup": "cd /project && bash scripts/auto_backup.sh",
}

_CRON_SCHEDULE_RE = re.compile(r'^[\d\*/,\-]+(\s+[\d\*/,\-]+){4}$')


# --- Tool definitions ---

TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from the BeStupid repo (logs, config, memory, scripts)",
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
        "description": "Write or update a file (only content/logs/, memory/, ~/.bestupid-private/)",
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
        "input_schema": {"type": "object", "properties": {}}
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
                    "description": "If true, regenerate current week's protocol"
                }
            }
        }
    },
    {
        "name": "get_brain_status",
        "description": "Get current status: priorities, health check, today's workout, blockers",
        "input_schema": {"type": "object", "properties": {}}
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
                "days": {"type": "integer", "default": 30, "description": "Days to search back"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "manage_cron",
        "description": "Manage cron jobs. For 'add', command_name must be one of: morning_briefing, evening_reminder, daily_planner, auto_backup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "remove"],
                    "description": "Action to perform"
                },
                "schedule": {
                    "type": "string",
                    "description": "Cron expression, e.g. '0 7 * * *' (required for 'add')"
                },
                "command_name": {
                    "type": "string",
                    "enum": list(ALLOWED_CRON_COMMANDS.keys()),
                    "description": "Predefined command to schedule (required for 'add')"
                },
                "line_number": {
                    "type": "integer",
                    "description": "Line number to remove (required for 'remove')"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from repo root"},
                "pattern": {"type": "string", "default": "*", "description": "Glob pattern"}
            },
            "required": ["path"]
        }
    },
    # --- 3 new tools ---
    {
        "name": "grep_files",
        "description": "Regex search across files in the repo. Returns file:line: content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "default": ".", "description": "Relative path to search in"},
                "file_glob": {"type": "string", "default": "*.md", "description": "File glob pattern"}
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "run_memory_command",
        "description": "Run a memory.py command, e.g. 'people add \"John\" --role accountant' or 'search \"protein\"'",
        "input_schema": {
            "type": "object",
            "properties": {
                "args": {"type": "string", "description": "Arguments to pass to memory.py"}
            },
            "required": ["args"]
        }
    },
    {
        "name": "run_script",
        "description": "Run a Python script from the scripts/ directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "script_name": {"type": "string", "description": "Script filename, e.g. 'brain.py'"},
                "args": {"type": "string", "default": "", "description": "Arguments to pass"}
            },
            "required": ["script_name"]
        }
    },
]


# --- Tool dispatcher ---

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
        return run_weekly_planner(this_week=inputs.get("this_week", False))
    elif name == "get_brain_status":
        return get_brain_status()
    elif name == "capture_to_inbox":
        return capture_to_inbox(inputs["text"])
    elif name == "search_logs":
        return search_logs(inputs["query"], inputs.get("days", 30))
    elif name == "manage_cron":
        return manage_cron(inputs["action"], inputs.get("schedule"), inputs.get("command_name"), inputs.get("line_number"))
    elif name == "list_files":
        return list_files(inputs["path"], inputs.get("pattern", "*"))
    elif name == "grep_files":
        return grep_files(inputs["pattern"], inputs.get("path", "."), inputs.get("file_glob", "*.md"))
    elif name == "run_memory_command":
        return run_memory_command(inputs["args"])
    elif name == "run_script":
        return run_script(inputs["script_name"], inputs.get("args", ""))

    return f"Unknown tool: {name}"


# --- Tool implementations ---

def read_file(path: str) -> str:
    if path.startswith("~"):
        full_path = Path(path).expanduser()
    else:
        full_path = REPO_ROOT / path

    err = _check_readable(full_path)
    if err:
        return err

    if full_path.exists():
        return full_path.read_text()
    return f"File not found: {path}"


def write_file(path: str, content: str) -> str:
    if path.startswith("~"):
        full_path = Path(path).expanduser()
    else:
        full_path = REPO_ROOT / path

    err = _check_writable(full_path)
    if err:
        return err

    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    return f"Wrote {len(content)} bytes to {path}"


def list_files(path: str, pattern: str = "*") -> str:
    full_path = REPO_ROOT / path
    if not full_path.exists():
        return f"Directory not found: {path}"
    files = sorted(full_path.glob(pattern))
    return "\n".join(f.name for f in files[-20:])


def update_metric_in_log(field: str, value: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = REPO_ROOT / "content" / "logs" / f"{today}.md"

    if not log_path.exists():
        return f"Today's log doesn't exist ({today}.md). Run daily planner first."

    content = log_path.read_text()
    pattern = rf"^{field}::.*$"
    replacement = f"{field}:: {value}"
    new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)

    if count > 0:
        log_path.write_text(new_content)
        return f"Updated {field}:: {value}"

    if "## Quick Log" in content:
        new_content = content.replace("## Quick Log", f"## Quick Log\n{field}:: {value}")
        log_path.write_text(new_content)
        return f"Added {field}:: {value} to Quick Log section"

    return f"Field '{field}::' not found in today's log."


def run_daily_planner() -> str:
    try:
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
    try:
        original_cwd = os.getcwd()
        os.chdir(str(REPO_ROOT))
        from weekly_planner import create_weekly_protocol
        result = create_weekly_protocol(this_week=this_week)
        os.chdir(original_cwd)
        return f"Weekly protocol created: {result}"
    except ImportError:
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
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    day_name = today.strftime("%A")

    output = [f"## Brain Status - {day_name}, {today_str}\n"]

    log_path = REPO_ROOT / "content" / "logs" / f"{today_str}.md"
    if log_path.exists():
        log_content = log_path.read_text()

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
        output.append("*Today's log doesn't exist yet. Run daily planner to create it.*\n")

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

        warnings = summary.get("recommendations", {}).get("warnings", [])
        if warnings:
            output.append("### Warnings")
            for w in warnings:
                output.append(f"- {w}")
            output.append("")

        streaks = summary.get("streaks", {})
        if streaks.get("current_streak"):
            status = "positive" if streaks["current_streak"] > 0 else "needs attention"
            output.append(f"### Streak: {abs(streaks['current_streak'])} days ({status})\n")
    except Exception as e:
        output.append(f"*Metrics analysis unavailable: {e}*\n")

    try:
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        monday_str = monday.strftime("%Y-%m-%d")
        protocol_path = REPO_ROOT / "content" / "config" / f"protocol_{monday_str}.md"

        if protocol_path.exists():
            protocol_content = protocol_path.read_text()
            output.append("### Today's Planned Workout")
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

    inbox_path = PRIVATE_DIR / "inbox.md"
    if inbox_path.exists():
        inbox_content = inbox_path.read_text()
        inbox_items = len([l for l in inbox_content.split("\n") if l.strip().startswith("- [")])
        if inbox_items > 0:
            output.append(f"### Inbox: {inbox_items} pending items\n")

    return "\n".join(output)


def capture_to_inbox(text: str) -> str:
    inbox_path = PRIVATE_DIR / "inbox.md"
    inbox_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- [{timestamp}] {text}\n"

    if not inbox_path.exists():
        inbox_path.write_text("# Inbox\n\n<!-- New items -->\n")

    with open(inbox_path, "a") as f:
        f.write(entry)

    return f"Captured: {text}"


def search_logs(query: str, days: int = 30) -> str:
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
            for line in content.split("\n"):
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


def manage_cron(action: str, schedule: str = None, command_name: str = None, line_number: int = None) -> str:
    ENV_SOURCE = ". /home/botuser/.cron_env; "

    if action == "list":
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout.strip():
            return "No cron jobs configured."
        lines = [l for l in result.stdout.strip().split("\n") if l.strip() and not l.startswith("#")]
        if not lines:
            return "No cron jobs configured."
        return "Current cron jobs:\n" + "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))

    elif action == "add":
        if not schedule or not command_name:
            return "Error: 'schedule' and 'command_name' are required for add."
        if not _CRON_SCHEDULE_RE.match(schedule):
            return f"Invalid cron schedule: {schedule}. Use 5 fields with digits, *, /, -, commas only."
        if command_name not in ALLOWED_CRON_COMMANDS:
            return f"Unknown command_name: {command_name}. Allowed: {', '.join(ALLOWED_CRON_COMMANDS.keys())}"

        command = ALLOWED_CRON_COMMANDS[command_name]
        cron_line = f"{schedule} {ENV_SOURCE}{command}"

        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
        new_crontab = existing.rstrip("\n") + "\n" + cron_line + "\n"

        proc = subprocess.run(["crontab", "-"], input=new_crontab, capture_output=True, text=True)
        if proc.returncode != 0:
            return f"Error setting crontab: {proc.stderr}"
        return f"Added cron job: {cron_line}"

    elif action == "remove":
        if line_number is None:
            return "Error: 'line_number' is required for remove."
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode != 0:
            return "No cron jobs to remove."
        all_lines = result.stdout.strip().split("\n")
        job_lines = [(i, l) for i, l in enumerate(all_lines) if l.strip() and not l.startswith("#")]
        if line_number < 1 or line_number > len(job_lines):
            return f"Invalid line number. Valid range: 1-{len(job_lines)}"
        removed = job_lines[line_number - 1]
        all_lines.pop(removed[0])
        new_crontab = "\n".join(all_lines) + "\n" if all_lines else ""
        proc = subprocess.run(["crontab", "-"], input=new_crontab, capture_output=True, text=True)
        if proc.returncode != 0:
            return f"Error updating crontab: {proc.stderr}"
        return f"Removed: {removed[1]}"

    return f"Unknown action: {action}"


# --- 3 new tools ---

_GREP_EXCLUDE = {".git", ".env", "node_modules", "__pycache__"}


def grep_files(pattern: str, path: str = ".", file_glob: str = "*.md") -> str:
    search_root = REPO_ROOT / path
    if not search_root.exists():
        return f"Path not found: {path}"

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex: {e}"

    results = []
    for filepath in search_root.rglob(file_glob):
        # Skip excluded dirs
        parts = filepath.relative_to(REPO_ROOT).parts
        if any(excl in parts for excl in _GREP_EXCLUDE):
            continue
        if any(excl in filepath.name for excl in [".env"]):
            continue

        try:
            text = filepath.read_text(errors="ignore")
            for i, line in enumerate(text.split("\n"), 1):
                if regex.search(line):
                    rel = filepath.relative_to(REPO_ROOT)
                    results.append(f"{rel}:{i}: {line.strip()}")
                    if len(results) >= 50:
                        return f"Found {len(results)}+ matches (capped at 50):\n" + "\n".join(results)
        except (OSError, UnicodeDecodeError):
            continue

    if results:
        return f"Found {len(results)} matches:\n" + "\n".join(results)
    return f"No matches for '{pattern}' in {path} ({file_glob})"


def run_memory_command(args: str) -> str:
    memory_script = SCRIPTS_DIR / "memory.py"
    if not memory_script.exists():
        return "Error: memory.py not found in scripts/"

    try:
        parsed_args = shlex.split(args)
    except ValueError as e:
        return f"Error parsing args: {e}"

    cmd = ["python", str(memory_script)] + parsed_args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=30, shell=False,
        )
        output = (result.stdout + result.stderr).strip()
        return output if output else "Command completed (no output)."
    except subprocess.TimeoutExpired:
        return "Memory command timed out (30s)."
    except Exception as e:
        return f"Error running memory command: {e}"


def run_script(script_name: str, args: str = "") -> str:
    # Validate script name
    if ".." in script_name or "/" in script_name or "\\" in script_name:
        return "Error: invalid script name (no paths allowed)."
    if not script_name.endswith(".py"):
        return "Error: only .py scripts are allowed."

    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return f"Script not found: scripts/{script_name}"

    try:
        parsed_args = shlex.split(args) if args else []
    except ValueError as e:
        return f"Error parsing args: {e}"

    cmd = ["python", str(script_path)] + parsed_args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=60, shell=False,
        )
        output = (result.stdout + result.stderr).strip()
        if len(output) > 5000:
            output = output[:5000] + "\n...(truncated)"
        return output if output else "Script completed (no output)."
    except subprocess.TimeoutExpired:
        return f"Script timed out (60s): {script_name}"
    except Exception as e:
        return f"Error running script: {e}"
