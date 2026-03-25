"""
Production-safe tool registry for BeStupid V2.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time as time_module
from datetime import datetime, timedelta
from pathlib import Path

from v2.bootstrap import get_services
from v2.app.timezone_resolver import parse_timezone_spec

from agent_policy import apply_agent_policy_update, format_agent_policy, load_agent_policy
from config import CRON_CONFIG, PRIVATE_DIR, PROJECT_ROOT

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
REPO_ROOT = PROJECT_ROOT

BLOCKED_PATTERNS = [".env", ".git/", ".git\\", "__pycache__"]

ALLOWED_CRON_COMMANDS = {
    "morning_briefing": "cd /project && python scripts/send_routine_reminder.py morning",
    "evening_reminder": "cd /project && python scripts/send_routine_reminder.py evening_start",
    "evening_screens": "cd /project && python scripts/send_routine_reminder.py evening_screens",
    "evening_bed": "cd /project && python scripts/send_routine_reminder.py evening_bed",
    "daily_planner": "cd /project && python scripts/daily_planner.py",
    "auto_backup": "cd /project && python scripts/robust_git_backup.py",
    "brain_pattern_detection": "cd /project && python scripts/brain_db.py patterns",
    "weekly_planner": "cd /project && python scripts/weekly_planner.py --this-week",
}
_CRON_SCHEDULE_RE = re.compile(r'^[\d\*/,\-]+(\s+[\d\*/,\-]+){4}$')
_GREP_EXCLUDE = {".git", ".env", "node_modules", "__pycache__"}

ALLOWED_METRICS = ["Weight", "Sleep", "Sleep_Quality", "Mood_AM", "Mood_PM", "Energy", "Focus"]


# --- Security: path restrictions ---

def _default_readable_prefixes() -> list[Path]:
    return [
        REPO_ROOT / "content",
        REPO_ROOT / "memory",
        REPO_ROOT / "scripts",
        REPO_ROOT / "telegram-bot",
        REPO_ROOT / "logs",
        REPO_ROOT / "data",
        REPO_ROOT / "docs",
        PRIVATE_DIR,
    ]


def _default_writable_prefixes() -> list[Path]:
    return [
        REPO_ROOT / "content" / "logs",
        REPO_ROOT / "memory",
        REPO_ROOT / "scripts",
        REPO_ROOT / "logs",
        PRIVATE_DIR,
    ]


def _is_path_blocked(path: Path) -> bool:
    s = str(path)
    return any(pat in s for pat in BLOCKED_PATTERNS)


def _check_readable(path: Path) -> str | None:
    """Return error string if path is not readable, else None."""
    resolved = path.resolve()
    if _is_path_blocked(resolved):
        return f"Access denied: {path}"
    for prefix in _default_readable_prefixes():
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
    for prefix in _default_writable_prefixes():
        try:
            resolved.relative_to(prefix.resolve())
            return None
        except ValueError:
            continue
    return f"Access denied: {path} is not in an allowed write path"

TOOLS = [
    {
        "name": "think",
        "description": (
            "Use this tool to reason through your approach BEFORE acting. Write down: "
            "what you know, what you need to find out, what steps you'll take, and "
            "which specific rules or constraints apply. ALWAYS use this before "
            "multi-step tasks or when tool results need interpretation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "thought": {
                    "type": "string",
                    "description": "Your reasoning, plan, or analysis",
                }
            },
            "required": ["thought"],
        },
    },
    {
        "name": "get_day_snapshot",
        "description": "Get the canonical snapshot for the current local day or a specific YYYY-MM-DD day.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Optional YYYY-MM-DD date in the user's local timezone."},
            },
        },
    },
    {
        "name": "set_timezone",
        "description": "Update the user's current timezone using an IANA zone like America/New_York or an offset like UTC-5.",
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone": {"type": "string", "description": "IANA timezone or UTC offset."},
                "location_label": {"type": "string", "description": "Optional short location label."},
            },
            "required": ["timezone"],
        },
    },
    {
        "name": "update_day_metric",
        "description": "Write a validated day metric into canonical state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": ALLOWED_METRICS},
                "value": {"type": "string"},
                "date": {"type": "string", "description": "Optional YYYY-MM-DD in local time."},
            },
            "required": ["field", "value"],
        },
    },
    {
        "name": "mark_habit",
        "description": "Mark a habit as done, pending, skipped, or snoozed for the current local day.",
        "input_schema": {
            "type": "object",
            "properties": {
                "habit_id": {"type": "string"},
                "status": {"type": "string", "enum": ["pending", "done", "skipped", "snoozed"]},
                "date": {"type": "string", "description": "Optional YYYY-MM-DD in local time."},
            },
            "required": ["habit_id", "status"],
        },
    },
    {
        "name": "create_open_loop",
        "description": "Create a follow-up, task, or reminder in canonical state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "kind": {"type": "string", "enum": ["task", "question", "followup", "habit", "correction"]},
                "priority": {"type": "string", "enum": ["low", "normal", "high"], "default": "normal"},
                "due_hours": {"type": "integer", "description": "Optional number of hours from now."},
            },
            "required": ["title", "kind"],
        },
    },
    {
        "name": "complete_open_loop",
        "description": "Complete an existing open loop by id or exact title.",
        "input_schema": {
            "type": "object",
            "properties": {
                "loop_id_or_title": {"type": "string"},
            },
            "required": ["loop_id_or_title"],
        },
    },
    {
        "name": "list_due_followups",
        "description": "List currently due open loops and follow-ups.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_stale_loops",
        "description": "List zombie tasks: open loops older than N days that may need scoping down, a hard deadline, or killing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "age_days": {"type": "integer", "description": "Minimum age in days (default 3)"},
            },
        },
    },
    {
        "name": "create_intervention",
        "description": "Start a behavioral experiment. Record a strategy, capture baseline metric value, and set an evaluation date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "strategy": {"type": "string", "description": "What you're trying (e.g., 'No screens after 9pm')"},
                "target_metric": {"type": "string", "enum": ["Weight", "Sleep", "Sleep_Quality", "Mood_AM", "Mood_PM", "Energy", "Focus"]},
                "duration_days": {"type": "integer", "default": 7, "description": "Days before evaluation (default 7)"},
            },
            "required": ["strategy", "target_metric"],
        },
    },
    {
        "name": "evaluate_intervention",
        "description": "Evaluate whether a tracked strategy changed the target metric. Compare current value to baseline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "intervention_id": {"type": "string"},
            },
            "required": ["intervention_id"],
        },
    },
    {
        "name": "list_interventions",
        "description": "List tracked strategy interventions, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["active", "evaluated", "dropped"]},
            },
        },
    },
    {
        "name": "manage_memory",
        "description": (
            "Manage memory candidates: queue new candidates from text, or approve/reject a pending candidate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["queue", "approve", "reject"]},
                "text": {"type": "string", "description": "Text to extract memory candidates from (required for 'queue')."},
                "candidate_id": {"type": "string", "description": "Candidate ID (required for 'approve'/'reject')."},
            },
            "required": ["action"],
        },
    },
    # --- Ported from tools.py (v1) ---
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
        "description": "Manage persistent cron jobs. Jobs survive container restarts. command_name must be one of: morning_briefing, evening_reminder, evening_screens, evening_bed, daily_planner, auto_backup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "remove", "enable", "disable"],
                    "description": "Action to perform"
                },
                "schedule": {
                    "type": "string",
                    "description": "Cron expression, e.g. '0 7 * * *' (required for 'add')"
                },
                "command_name": {
                    "type": "string",
                    "enum": list(ALLOWED_CRON_COMMANDS.keys()),
                    "description": "Predefined command (required for add/remove/enable/disable)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "run_script",
        "description": "Run a Python (.py) or Bash (.sh) script from scripts/ or ~/.bestupid-private/",
        "input_schema": {
            "type": "object",
            "properties": {
                "script_name": {"type": "string", "description": "Script filename e.g. 'brain.py', 'auto_backup.sh', or '~/.bestupid-private/my_script.py'"},
                "args": {"type": "string", "default": "", "description": "Arguments to pass"}
            },
            "required": ["script_name"]
        }
    },
    {
        "name": "search_conversation_history",
        "description": "Search through past conversation history for messages matching a query. Use this to recall previous discussions, decisions, or information shared in past conversations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term or phrase to find in conversation history"},
                "limit": {"type": "integer", "default": 20, "description": "Maximum number of matching messages to return"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_system_status",
        "description": "Get system status including git state, recent backup failures, and scheduled jobs. Use this to diagnose issues.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_current_datetime",
        "description": "Get the current date and time with timezone info. Use this to verify the date before creating logs or scheduling.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "check_git_health",
        "description": "Check git health: branch, remote URL, auth status, sync state. Use this to diagnose git/backup issues.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "sync_with_remote",
        "description": "Pull latest changes from remote (rebase). Safe to run anytime - preserves local changes.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "manage_policy",
        "description": "Get or update assistant operating policy for this chat. Use to adapt behavior after recurring friction.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "append_rules", "replace_rules", "set_focus", "reset"],
                    "description": "Policy action"
                },
                "rules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Behavior rules to append/replace"
                },
                "focus": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Focus priorities to set"
                },
                "reason": {
                    "type": "string",
                    "description": "Why this update is needed based on observed outcomes"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "fact_check",
        "description": (
            "Verify a claim against stored knowledge: memory (people, projects, decisions, commitments), "
            "daily logs, and conversation history. Returns evidence for/against with a verdict. "
            "Use this when Ryan states something that should be verified, or when you want to "
            "confirm facts before acting on them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim": {
                    "type": "string",
                    "description": "The claim or statement to verify, e.g. 'I committed to calling John by Friday'"
                },
                "sources": {
                    "type": "string",
                    "default": "all",
                    "description": "Comma-separated sources to check: memory, logs, history, or all"
                },
                "days": {
                    "type": "integer",
                    "default": 30,
                    "description": "How many days back to search in logs"
                }
            },
            "required": ["claim"]
        }
    },
    {
        "name": "semantic_search",
        "description": (
            "Search the second brain using semantic similarity + keyword matching. "
            "Finds relevant documents even without exact keyword matches. "
            "Use this for questions like 'what did I decide about X?' or 'what do I know about Y?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query"
                },
                "doc_type": {
                    "type": "string",
                    "description": "Filter by type: conversation, log_entry, article, note, entity. Leave empty for all.",
                    "default": ""
                },
                "limit": {
                    "type": "integer",
                    "default": 5,
                    "description": "Maximum results to return"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "ingest_content",
        "description": (
            "Ingest content into the second brain. Stores the document, extracts entities "
            "and relationships, and generates semantic embeddings. Use for articles, notes, ideas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The text content to ingest"
                },
                "title": {
                    "type": "string",
                    "default": "",
                    "description": "Title for the content"
                },
                "doc_type": {
                    "type": "string",
                    "default": "note",
                    "description": "Type: note, article, idea"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "explore_connections",
        "description": (
            "Explore entity connections in the knowledge graph. Find entities related to a given "
            "name and see how they connect (1-2 hops). Good for questions like 'what's connected to project X?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Name of the entity to explore connections for"
                },
                "hops": {
                    "type": "integer",
                    "default": 1,
                    "description": "Connection depth (1 or 2)"
                }
            },
            "required": ["entity_name"]
        }
    },
    {
        "name": "brain_stats",
        "description": "Get statistics about the second brain: document counts, entity counts, pattern counts.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "log_food",
        "description": (
            "Log a food item and get estimated macros. Estimates calories, protein, carbs, fat, fiber "
            "using LLM, appends to today's Fuel Log, and returns the estimate with running daily totals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "food_description": {
                    "type": "string",
                    "description": "What was eaten, e.g. '2 eggs and toast with butter'"
                }
            },
            "required": ["food_description"]
        }
    },
    {
        "name": "get_nutrition_summary",
        "description": "Get daily nutrition totals (calories, protein, carbs, fat, fiber) from food log entries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Specific YYYY-MM-DD date, or omit for last N days"},
                "days": {"type": "integer", "default": 7, "description": "Number of days if no specific date"},
            },
        },
    },
    {
        "name": "run_query",
        "description": (
            "Execute a read-only SQL query against assistant_state or brain databases. "
            "Returns up to 200 rows. Use PRAGMA table_info(table_name) for schema discovery. "
            "Blocked: INSERT, UPDATE, DELETE, ATTACH, or any write operation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "db": {
                    "type": "string",
                    "enum": ["state", "brain"],
                    "description": "Database to query: 'state' (day tracking) or 'brain' (documents, entities)"
                },
                "sql": {"type": "string", "description": "SQL query to execute (read-only)"},
            },
            "required": ["db", "sql"],
        },
    },
    {
        "name": "analyze_metrics",
        "description": (
            "Analyze tracked metrics. Use analysis_type='trend' for time series & trend, "
            "'correlation' for Pearson correlation between two metrics, "
            "'insights' for computed insights (weight trend, TDEE, patterns)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "analysis_type": {"type": "string", "enum": ["trend", "correlation", "insights"]},
                "field": {"type": "string", "enum": ALLOWED_METRICS, "description": "Metric field (for trend)"},
                "field_a": {"type": "string", "enum": ALLOWED_METRICS, "description": "First metric (for correlation)"},
                "field_b": {"type": "string", "enum": ALLOWED_METRICS, "description": "Second metric (for correlation)"},
                "days": {"type": "integer", "default": 30, "description": "Number of days to analyze"},
            },
            "required": ["analysis_type"],
        },
    },
    {
        "name": "habit_completion",
        "description": "Get completion rate and streak info for a specific habit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "habit_name": {"type": "string", "description": "Habit name (case-insensitive match)"},
                "days": {"type": "integer", "default": 30, "description": "Number of days to analyze"},
            },
            "required": ["habit_name"],
        },
    },
    {
        "name": "log_workout",
        "description": (
            "Log a workout session with optional exercises and cardio activities. "
            "Use for strength training, runs, swims, bike rides, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "workout_type": {
                    "type": "string",
                    "description": "Type of workout: strength, run, swim, bike, yoga, recovery, etc."
                },
                "exercises": {
                    "type": "array",
                    "description": "Strength exercises: [{name, sets, reps, weight_lbs}]",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "sets": {"type": "integer"},
                            "reps": {"type": "integer"},
                            "weight_lbs": {"type": "number"},
                        },
                        "required": ["name"],
                    },
                },
                "cardio": {
                    "type": "array",
                    "description": "Cardio activities: [{type, distance, distance_unit, duration_minutes, avg_hr}]",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "distance": {"type": "number"},
                            "distance_unit": {"type": "string", "default": "mi"},
                            "duration_minutes": {"type": "number"},
                            "avg_hr": {"type": "integer"},
                        },
                        "required": ["type"],
                    },
                },
                "notes": {"type": "string", "description": "Optional workout notes"},
                "date": {"type": "string", "description": "Optional YYYY-MM-DD in local time"},
            },
            "required": ["workout_type"],
        },
    },
    # --- Daily Todo Tools ---
    {
        "name": "create_todo",
        "description": "Create a daily todo item. Use category to set priority tier.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "The todo text."},
                "category": {"type": "string", "enum": ["must_win", "can_do", "not_today", ""], "description": "Priority category."},
                "date": {"type": "string", "description": "Optional YYYY-MM-DD. Defaults to today."},
                "is_top3": {"type": "boolean", "description": "True if this is a 'priority for tomorrow' item."},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_todo",
        "description": "Complete or drop (cancel) a daily todo by ID or title match.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["complete", "drop"]},
                "todo_id_or_title": {"type": "string", "description": "Loop ID or title of the todo."},
                "notes": {"type": "string", "description": "Optional reason (only used for drop)."},
            },
            "required": ["action", "todo_id_or_title"],
        },
    },
    {
        "name": "defer_todo",
        "description": "Defer a daily todo to a future date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_id_or_title": {"type": "string", "description": "Loop ID or title of the todo to defer."},
                "to_date": {"type": "string", "description": "YYYY-MM-DD date to defer to."},
            },
            "required": ["todo_id_or_title", "to_date"],
        },
    },
    {
        "name": "list_todos",
        "description": "List daily todos for a given date with optional status filter.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Optional YYYY-MM-DD. Defaults to today."},
                "status": {"type": "string", "enum": ["open", "completed", "rolled", "cancelled"], "description": "Optional status filter."},
            },
        },
    },
    {
        "name": "set_priorities",
        "description": "Set evening priority items for tomorrow. Creates daily_todo entries with is_top3=true.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}, "description": "List of priority items for tomorrow."},
                "date": {"type": "string", "description": "Optional YYYY-MM-DD for the target date. Defaults to tomorrow."},
            },
            "required": ["items"],
        },
    },
    # --- Agent-Parity Tools ---
    {
        "name": "close_day",
        "description": "Close the current day in canonical state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Optional YYYY-MM-DD. Defaults to today."},
            },
        },
    },
    {
        "name": "snooze_loop",
        "description": "Snooze an open loop for a number of minutes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "loop_id_or_title": {"type": "string", "description": "Loop ID or title to snooze."},
                "minutes": {"type": "integer", "description": "Minutes to snooze. Default 60."},
            },
            "required": ["loop_id_or_title"],
        },
    },
    {
        "name": "manage_habit",
        "description": "Create, disable, enable, or rename a habit definition.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create", "disable", "enable", "rename"]},
                "name": {"type": "string", "description": "Habit name (or ID for existing habits)."},
                "new_name": {"type": "string", "description": "New name when action is 'rename'."},
                "cadence": {"type": "string", "description": "Cadence for new habits. Default 'daily'."},
            },
            "required": ["action", "name"],
        },
    },
    {
        "name": "save_reflection",
        "description": "Save evening reflection (what went well, what went poorly, lessons).",
        "input_schema": {
            "type": "object",
            "properties": {
                "went_well": {"type": "string", "description": "What went well today."},
                "went_poorly": {"type": "string", "description": "What went poorly today."},
                "lessons": {"type": "string", "description": "Lessons learned today."},
                "date": {"type": "string", "description": "Optional YYYY-MM-DD. Defaults to today."},
            },
        },
    },
    {
        "name": "get_reflections",
        "description": "Get evening reflections for a given date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Optional YYYY-MM-DD. Defaults to today."},
            },
        },
    },
    {
        "name": "manage_coaching",
        "description": "Mute or unmute coaching heartbeat. For mute, optionally specify minutes (default 60, max 1440).",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["mute", "unmute"]},
                "minutes": {"type": "integer", "description": "Minutes to mute (only for 'mute' action). Default 60. Max 1440."},
            },
            "required": ["action"],
        },
    },
    {
        "name": "get_token_usage",
        "description": "Get current token usage and daily budget status.",
        "input_schema": {"type": "object", "properties": {}},
        "cache_control": {"type": "ephemeral"},
    },
    {
        "name": "decompose_goal",
        "description": "Break a high-level goal into sub-tasks. Creates a parent loop and child loops linked to it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "The high-level goal to decompose"},
                "subtasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of sub-task titles",
                },
            },
            "required": ["goal", "subtasks"],
        },
    },
    {
        "name": "goal_progress",
        "description": "Show progress on a goal and its sub-tasks. Returns hierarchical completion status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id_or_title": {"type": "string", "description": "Parent goal loop_id or title"},
            },
            "required": ["goal_id_or_title"],
        },
    },
    {
        "name": "refresh_context",
        "description": "Re-fetch the current day context after making multiple writes. Returns updated snapshot.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "self_reflect",
        "description": "Record an observation about your own performance, patterns noticed, or coaching effectiveness. Use after sessions where something worked well or poorly.",
        "input_schema": {
            "type": "object",
            "properties": {
                "observation": {
                    "type": "string",
                    "description": "What you observed about your coaching effectiveness or patterns",
                },
            },
            "required": ["observation"],
        },
    },
]

# ---------------------------------------------------------------------------
# Lazy tool loading: core vs. extended
# ---------------------------------------------------------------------------

# Core tools always sent to the API (high-frequency daily use)
CORE_TOOL_NAMES = {
    "think",
    "get_day_snapshot",
    "update_day_metric",
    "mark_habit",
    "log_food",
    "get_nutrition_summary",
    "create_open_loop",
    "complete_open_loop",
    "create_todo",
    "update_todo",
    "list_todos",
    "list_due_followups",
    "analyze_metrics",
    "read_file",
    "write_file",
    "search_logs",
    "semantic_search",
    "manage_policy",
    "save_reflection",
    "decompose_goal",
    "goal_progress",
    "refresh_context",
    "self_reflect",
    "list_extended_tools",  # The meta-tool itself is always available
}

# Meta-tool for discovering extended tools
_LIST_EXTENDED_TOOLS_DEF = {
    "name": "list_extended_tools",
    "description": "List all available extended tools not in the core set. Call this when you need a tool that isn't available. Returns tool names and descriptions.",
    "input_schema": {"type": "object", "properties": {}},
}


def get_core_tools() -> list[dict]:
    """Return core tool definitions + the meta-tool."""
    core = [t for t in TOOLS if t["name"] in CORE_TOOL_NAMES]
    if not any(t["name"] == "list_extended_tools" for t in core):
        core.append(_LIST_EXTENDED_TOOLS_DEF)
    # Ensure cache_control is on the last tool
    for t in core:
        t.pop("cache_control", None)
    core[-1]["cache_control"] = {"type": "ephemeral"}
    return core


def get_extended_tool_descriptions() -> str:
    """Return names + descriptions of extended tools."""
    extended = [t for t in TOOLS if t["name"] not in CORE_TOOL_NAMES]
    if not extended:
        return "No extended tools available."
    lines = ["Extended tools (call any by name after viewing this list):"]
    for t in extended:
        desc = t.get("description", "")
        if len(desc) > 100:
            desc = desc[:100] + "..."
        lines.append(f"- {t['name']}: {desc}")
    return "\n".join(lines)


def get_all_tools() -> list[dict]:
    """Return all tool definitions (core + extended). Used when extended tools are activated."""
    all_tools = list(TOOLS)
    if not any(t["name"] == "list_extended_tools" for t in all_tools):
        all_tools.append(_LIST_EXTENDED_TOOLS_DEF)
    for t in all_tools:
        t.pop("cache_control", None)
    all_tools[-1]["cache_control"] = {"type": "ephemeral"}
    return all_tools


def _resolve_local_date(chat_id: int, maybe_date: str | None) -> str:
    services = get_services()
    if maybe_date:
        return maybe_date
    return services.timezone_resolver.resolve_now(chat_id).local_date


def get_day_snapshot(chat_id: int, date: str | None = None) -> str:
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    snapshot = services.store.get_day_snapshot(chat_id, local_date)
    if not snapshot:
        resolved = services.timezone_resolver.resolve_now(chat_id)
        services.store.ensure_day_open(resolved)
        snapshot = services.store.get_day_snapshot(chat_id, local_date)
    if not snapshot:
        return "No day snapshot available."

    lines = [
        f"Day: {snapshot.local_date}",
        f"Timezone: {snapshot.timezone}",
        f"Status: {snapshot.status}",
        f"State version: {snapshot.state_version}",
    ]
    if snapshot.metrics:
        lines.append("Metrics:")
        for key, value in sorted(snapshot.metrics.items()):
            lines.append(f"- {key}: {value}")
    if snapshot.habits:
        lines.append("Habits:")
        for habit in snapshot.habits:
            lines.append(f"- {habit['name']}: {habit['status']}")
    if snapshot.open_loops:
        lines.append("Open loops:")
        for loop in snapshot.open_loops[:5]:
            lines.append(f"- [{loop['priority']}] {loop['title']}")
    return "\n".join(lines)


def set_timezone(chat_id: int, timezone: str, location_label: str | None = None) -> str:
    services = get_services()
    parsed = parse_timezone_spec(timezone)
    resolved = services.timezone_resolver.set_current_timezone(
        chat_id=chat_id,
        timezone=parsed.canonical_name,
        source="tool",
        location_label=location_label,
    )
    services.store.ensure_day_open(resolved)
    return f"Timezone updated to {resolved.timezone_label}. Local date is {resolved.local_date}."


def update_day_metric(chat_id: int, field: str, value: str, date: str | None = None) -> str:
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    result = services.store.set_day_metric(chat_id, local_date, field, value)
    snapshot = services.store.get_day_snapshot(chat_id, local_date)
    if snapshot:
        services.projection.render_private_day_log(snapshot.day_id)
    return f"Updated {field}={result['value']} for {local_date}. Stored value confirmed: {result['value']}"


def append_food(chat_id: int, description: str, date: str | None = None) -> str:
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    result = services.store.append_food(chat_id, local_date, description)
    snapshot = services.store.get_day_snapshot(chat_id, local_date)
    if snapshot:
        services.projection.render_private_day_log(snapshot.day_id)
    totals = _get_nutrition_totals_from_sqlite(chat_id, local_date)
    totals_line = f"Running totals: {totals['calories']} cal, {totals['protein_g']}g protein, {totals['carbs_g']}g carbs, {totals['fat_g']}g fat ({totals['count']} entries)"
    return f"Logged food for {local_date}: {result['description']}\n{totals_line}"


def _compact_habit_summary(chat_id: int, local_date: str) -> str:
    """Return a one-line habit summary like 'Habits: 3/7 done (yoga✓ writing✓ reading✗)'."""
    services = get_services()
    snapshot = services.store.get_day_snapshot(chat_id, local_date)
    if not snapshot:
        return ""
    habits = snapshot.get("habits", [])
    if not habits:
        return ""
    done = sum(1 for h in habits if h.get("status") == "done")
    total = len(habits)
    details = " ".join(
        f"{h['habit_id']}{'✓' if h.get('status') == 'done' else '✗'}"
        for h in habits
    )
    return f"Habits: {done}/{total} done ({details})"


def mark_habit(chat_id: int, habit_id: str, status: str, date: str | None = None) -> str:
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    result = services.store.mark_habit(chat_id, local_date, habit_id, status)
    snapshot = services.store.get_day_snapshot(chat_id, local_date)
    if snapshot:
        services.projection.render_private_day_log(snapshot.day_id)
    summary = _compact_habit_summary(chat_id, local_date)
    return f"Marked habit {result['habit_id']} as {result['status']} for {local_date}.\n{summary}"


def create_open_loop(chat_id: int, title: str, kind: str, priority: str = "normal", due_hours: int | None = None) -> str:
    services = get_services()
    resolved = services.timezone_resolver.resolve_now(chat_id)
    day = services.store.ensure_day_open(resolved)
    due_at = ""
    if due_hours is not None:
        due_at = (resolved.utc_now + timedelta(hours=max(1, due_hours))).isoformat()
    created = services.store.create_open_loop(
        chat_id=chat_id,
        title=title,
        kind=kind,
        priority=priority,
        due_at_utc=due_at,
        day_id=day["day_id"],
    )
    services.projection.render_private_day_log(day["day_id"])
    open_count = len(services.store.list_due_followups(chat_id, now_utc=services.clock.now_utc(), limit=100))
    return f"Created {kind} loop {created['loop_id']}: {created['title']}\nOpen loops: {open_count}"


def complete_open_loop(chat_id: int, loop_id_or_title: str) -> str:
    services = get_services()
    result = services.store.complete_open_loop(chat_id, loop_id_or_title)
    if not result:
        return f"No open loop found for {loop_id_or_title}."
    snapshot = services.store.get_day_snapshot(chat_id)
    if snapshot:
        services.projection.render_private_day_log(snapshot.day_id)
    open_count = len(services.store.list_due_followups(chat_id, now_utc=services.clock.now_utc(), limit=100))
    return f"Completed loop {result['loop_id']}: {result['title']}\nRemaining open loops: {open_count}"


def list_due_followups(chat_id: int) -> str:
    services = get_services()
    due = services.store.list_due_followups(chat_id, now_utc=services.clock.now_utc(), limit=10)
    if not due:
        return "No due follow-ups."
    lines = ["Due follow-ups:"]
    for item in due:
        due_suffix = f" due {item['due_at_utc']}" if item.get("due_at_utc") else ""
        lines.append(f"- {item['loop_id']}: [{item['priority']}] {item['title']}{due_suffix}")
    return "\n".join(lines)


def queue_memory_candidates(chat_id: int, text: str) -> str:
    services = get_services()
    session = services.store.get_or_create_session(chat_id)
    turn_id = services.store.record_turn(chat_id, session["session_id"], 0, "user", text)
    created = services.memory_review.extract_candidates(chat_id, turn_id, text)
    if not created:
        return "No reviewable memory candidates found."
    return "Queued memory candidates:\n" + "\n".join(
        f"- {item.candidate_id}: [{item.kind}] {item.payload}" for item in created
    )


def review_memory_candidate(chat_id: int, candidate_id: str, action: str) -> str:
    services = get_services()
    result = services.memory_review.review_candidate(chat_id, candidate_id, action)
    if not result:
        return f"Candidate not found: {candidate_id}"
    return f"Candidate {candidate_id} -> {result['status']}"


# --- Ported tool implementations from tools.py (v1) ---

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
    tmp_path = full_path.with_suffix(".tmp")
    tmp_path.write_text(content)
    tmp_path.rename(full_path)
    return f"Wrote {len(content)} bytes to {path}"


def list_files(path: str, pattern: str = "*") -> str:
    full_path = REPO_ROOT / path
    if not full_path.exists():
        return f"Directory not found: {path}"
    files = sorted(full_path.glob(pattern))
    return "\n".join(f.name for f in files[-20:])


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
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=120)
        if result.returncode == 0:
            return f"Weekly protocol created.\n{result.stdout}"
        return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error creating weekly protocol: {e}"


def get_brain_status(chat_id: int = 0) -> str:
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    day_name = today.strftime("%A")

    output = [f"## Brain Status - {day_name}, {today_str}\n"]

    # Todos + Metrics: read from SQLite
    services = get_services()
    snapshot = services.store.get_day_snapshot(chat_id, today_str)

    if snapshot and snapshot.todos:
        open_todos = [t for t in snapshot.todos if t.get("status") == "open"]
        done_todos = [t for t in snapshot.todos if t.get("status") == "completed"]
        if open_todos:
            output.append("### Incomplete Todos")
            for todo in open_todos[:10]:
                prefix = "[must_win] " if todo.get("category") == "must_win" else ""
                rollover = f" (rolled {todo['rollover_count']}x)" if int(todo.get("rollover_count", 0)) > 0 else ""
                output.append(f"- [ ] {prefix}{todo['title']}{rollover}")
            output.append("")
        if done_todos:
            output.append(f"### Completed: {len(done_todos)}/{len(snapshot.todos)}\n")

    if snapshot and snapshot.metrics:
        output.append("### Today's Metrics")
        for k, v in sorted(snapshot.metrics.items()):
            output.append(f"- {k}: {v}")
        output.append("")
    elif not snapshot:
        output.append("*Today's day is not open yet. Run daily planner to create it.*\n")

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

        # Search multiple locations and naming patterns for protocol files
        protocol_content = None
        search_dirs = [
            REPO_ROOT / "content" / "config",
            REPO_ROOT / "memory",
        ]
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for candidate in sorted(search_dir.glob(f"protocol_{monday_str}*"), reverse=True):
                protocol_content = candidate.read_text()
                break
            if protocol_content:
                break

        # If no protocol for this week, try last week's (still relevant early in the week)
        if not protocol_content:
            last_monday = monday - timedelta(days=7)
            last_monday_str = last_monday.strftime("%Y-%m-%d")
            for search_dir in search_dirs:
                if not search_dir.exists():
                    continue
                for candidate in sorted(search_dir.glob(f"protocol_{last_monday_str}*"), reverse=True):
                    protocol_content = candidate.read_text()
                    break
                if protocol_content:
                    break

        if protocol_content:
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


def _load_cron_config() -> dict:
    if CRON_CONFIG.exists():
        try:
            return json.loads(CRON_CONFIG.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cron_config(config: dict) -> None:
    CRON_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = CRON_CONFIG.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(config, indent=2) + "\n")
    tmp_path.rename(CRON_CONFIG)


def _sync_cron_to_scheduler() -> str | None:
    """Reload jobs in the Python scheduler. Returns error string or None."""
    try:
        from scheduler import reload_jobs
        reload_jobs()
        return None
    except Exception as e:
        return f"Error reloading scheduler: {e}"


def manage_cron(action: str, schedule: str = None, command_name: str = None) -> str:
    config = _load_cron_config()

    if action == "list":
        if not config:
            return "No cron jobs configured."
        lines = []
        for name, entry in config.items():
            status = "enabled" if entry.get("enabled") else "disabled"
            lines.append(f"- {name}: {entry['schedule']} [{status}]")
        return "Cron jobs:\n" + "\n".join(lines)

    elif action == "add":
        if not schedule or not command_name:
            return "Error: 'schedule' and 'command_name' are required for add."
        if not _CRON_SCHEDULE_RE.match(schedule):
            return f"Invalid cron schedule: {schedule}. Use 5 fields with digits, *, /, -, commas only."
        if command_name not in ALLOWED_CRON_COMMANDS:
            return f"Unknown command_name: {command_name}. Allowed: {', '.join(ALLOWED_CRON_COMMANDS.keys())}"
        config[command_name] = {"schedule": schedule, "enabled": True}
        _save_cron_config(config)
        err = _sync_cron_to_scheduler()
        if err:
            return err
        return f"Added cron job: {command_name} ({schedule})"

    elif action == "remove":
        if not command_name:
            return "Error: 'command_name' is required for remove."
        if command_name not in config:
            return f"Job '{command_name}' not found in config."
        del config[command_name]
        _save_cron_config(config)
        err = _sync_cron_to_scheduler()
        if err:
            return err
        return f"Removed cron job: {command_name}"

    elif action == "enable":
        if not command_name:
            return "Error: 'command_name' is required for enable."
        if command_name not in config:
            return f"Job '{command_name}' not found in config. Use 'add' first."
        config[command_name]["enabled"] = True
        _save_cron_config(config)
        err = _sync_cron_to_scheduler()
        if err:
            return err
        return f"Enabled cron job: {command_name}"

    elif action == "disable":
        if not command_name:
            return "Error: 'command_name' is required for disable."
        if command_name not in config:
            return f"Job '{command_name}' not found in config."
        config[command_name]["enabled"] = False
        _save_cron_config(config)
        err = _sync_cron_to_scheduler()
        if err:
            return err
        return f"Disabled cron job: {command_name}"

    return f"Unknown action: {action}"


def run_script(script_name: str, args: str = "") -> str:
    # Validate script name
    if ".." in script_name or "\\" in script_name:
        return "Error: invalid script name (no path traversal allowed)."

    # Allow both Python and Bash scripts
    is_python = script_name.endswith(".py")
    is_bash = script_name.endswith(".sh")
    if not (is_python or is_bash):
        return "Error: only .py and .sh scripts are allowed."

    # Allow scripts/ dir or ~/.bestupid-private/ paths
    if script_name.startswith("~/.bestupid-private/"):
        script_path = Path(script_name).expanduser()
        if ".." in str(script_path.resolve()):
            return "Error: invalid script path."
    elif "/" in script_name:
        return "Error: invalid script name (no paths allowed, except ~/.bestupid-private/)."
    else:
        script_path = SCRIPTS_DIR / script_name

    if not script_path.exists():
        return f"Script not found: {script_name}"

    try:
        parsed_args = shlex.split(args) if args else []
    except ValueError as e:
        return f"Error parsing args: {e}"

    # Use appropriate interpreter
    interpreter = "python" if is_python else "bash"
    cmd = [interpreter, str(script_path)] + parsed_args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=120, shell=False,  # 2 min timeout for bash
        )
        output = (result.stdout + result.stderr).strip()
        if len(output) > 5000:
            output = output[:5000] + "\n...(truncated)"
        return output if output else "Script completed (no output)."
    except subprocess.TimeoutExpired:
        return f"Script timed out (120s): {script_name}"
    except Exception as e:
        return f"Error running script: {e}"


def search_conversation_history(query: str, limit: int = 20, chat_id: int = 0) -> str:
    """Search conversation history via SQLite turn table."""
    services = get_services()
    rows = services.store.search_turns(chat_id or 0, query, limit=limit, days=30)

    if not rows:
        return f"No messages found matching '{query}'."

    matches = []
    for row in rows:
        role = row["role"]
        text = row["text"]
        preview = text[:500] + "..." if len(text) > 500 else text
        ts = row["created_at_utc"][:10] if row.get("created_at_utc") else ""
        matches.append(f"[{ts} {role}] {preview}")

    result = f"Found {len(matches)} message(s) matching '{query}':\n\n"
    result += "\n\n---\n\n".join(matches)
    return result


def get_system_status() -> str:
    """Get comprehensive system status for debugging."""
    lines = ["## System Status\n"]

    # Git info (using fast commands that don't scan working tree)
    try:
        # Read branch from .git/HEAD (fast, no subprocess)
        git_head = REPO_ROOT / ".git" / "HEAD"
        if git_head.exists():
            head_content = git_head.read_text().strip()
            if head_content.startswith("ref: refs/heads/"):
                branch = head_content.replace("ref: refs/heads/", "")
            else:
                branch = head_content[:8]  # Detached HEAD, show short hash
            lines.append(f"**Git Branch:** {branch}")

        # Get current commit (fast)
        git_rev = subprocess.run(
            ["git", "-c", "safe.directory=/project", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(REPO_ROOT)
        )
        if git_rev.returncode == 0:
            lines.append(f"**Current Commit:** {git_rev.stdout.strip()}")

        # Note: git status times out in container due to Docker volume performance
        lines.append("**Uncommitted Changes:** (use host git status - container times out)")
    except Exception as e:
        lines.append(f"**Git Info:** Error - {e}")

    # Backup failures log
    backup_log = REPO_ROOT / "logs" / "backup-failures.log"
    if backup_log.exists():
        try:
            content = backup_log.read_text()
            # Get last 500 chars
            recent = content[-500:] if len(content) > 500 else content
            lines.append(f"\n**Recent Backup Failures:**\n```\n{recent.strip()}\n```")
        except Exception as e:
            lines.append(f"\n**Backup Log:** Error reading - {e}")
    else:
        lines.append("\n**Backup Log:** No failures logged")

    # Scheduled jobs
    try:
        from scheduler import get_next_runs
        next_runs = get_next_runs()
        if next_runs:
            lines.append("\n**Scheduled Jobs:**")
            for name, next_run in next_runs.items():
                lines.append(f"- {name}: next run at {next_run}")
        else:
            lines.append("\n**Scheduled Jobs:** None configured")
    except Exception as e:
        lines.append(f"\n**Scheduled Jobs:** Error - {e}")

    # Heartbeat status
    try:
        from heartbeat import get_health_status
        lines.append("\n" + get_health_status())
    except Exception as e:
        lines.append(f"\n**Heartbeat:** Error - {e}")

    return "\n".join(lines)


def get_current_datetime() -> str:
    """Get current date/time with timezone info."""
    now = datetime.now()
    tz_name = time_module.tzname[time_module.daylight] if time_module.daylight else time_module.tzname[0]
    utc_offset = time_module.strftime("%z")

    return (
        f"**Current Date/Time:**\n"
        f"- Date: {now.strftime('%Y-%m-%d')}\n"
        f"- Time: {now.strftime('%H:%M:%S')}\n"
        f"- Day: {now.strftime('%A')}\n"
        f"- Timezone: {tz_name} (UTC{utc_offset[:3]}:{utc_offset[3:]})\n"
        f"- ISO: {now.isoformat()}"
    )


def check_git_health() -> str:
    """Check git health: branch, remote, auth, sync status."""
    lines = ["## Git Health Check\n"]

    # Branch
    git_head = REPO_ROOT / ".git" / "HEAD"
    if git_head.exists():
        head_content = git_head.read_text().strip()
        if head_content.startswith("ref: refs/heads/"):
            branch = head_content.replace("ref: refs/heads/", "")
        else:
            branch = f"DETACHED ({head_content[:8]})"
        lines.append(f"**Branch:** {branch}")
    else:
        lines.append("**Branch:** ERROR - .git/HEAD not found")

    # Remote URL
    try:
        result = subprocess.run(
            ["git", "-c", "safe.directory=/project", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5, cwd=str(REPO_ROOT)
        )
        if result.returncode == 0:
            remote_url = result.stdout.strip()
            is_ssh = remote_url.startswith("git@")
            protocol = "SSH" if is_ssh else "HTTPS"
            lines.append(f"**Remote:** {remote_url}")
            lines.append(f"**Protocol:** {protocol}")
        else:
            lines.append(f"**Remote:** ERROR - {result.stderr.strip()}")
    except Exception as e:
        lines.append(f"**Remote:** ERROR - {e}")

    # Auth test (SSH)
    try:
        result = subprocess.run(
            ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "git@github.com"],
            capture_output=True, text=True, timeout=10, cwd=str(REPO_ROOT)
        )
        # SSH -T returns exit code 1 even on success (no shell access granted)
        output = result.stderr.strip()
        if "successfully authenticated" in output.lower() or "Hi " in output:
            lines.append("**SSH Auth:** OK")
        elif "Permission denied" in output:
            lines.append("**SSH Auth:** FAILED - Permission denied (check SSH key)")
        elif "Host key verification failed" in output:
            lines.append("**SSH Auth:** FAILED - Host key verification (run ssh-keyscan)")
        else:
            lines.append(f"**SSH Auth:** UNKNOWN - {output[:100]}")
    except subprocess.TimeoutExpired:
        lines.append("**SSH Auth:** TIMEOUT (network issue?)")
    except Exception as e:
        lines.append(f"**SSH Auth:** ERROR - {e}")

    # Fetch to check sync (fast, doesn't download objects)
    try:
        result = subprocess.run(
            ["git", "-c", "safe.directory=/project", "fetch", "--dry-run"],
            capture_output=True, text=True, timeout=15, cwd=str(REPO_ROOT)
        )
        if result.returncode == 0:
            if result.stderr.strip():
                lines.append("**Sync Status:** Remote has new commits")
            else:
                lines.append("**Sync Status:** Up to date with remote")
        else:
            lines.append(f"**Sync Status:** FETCH ERROR - {result.stderr.strip()[:100]}")
    except subprocess.TimeoutExpired:
        lines.append("**Sync Status:** TIMEOUT (network issue?)")
    except Exception as e:
        lines.append(f"**Sync Status:** ERROR - {e}")

    return "\n".join(lines)


def sync_with_remote() -> str:
    """Pull latest changes from remote with rebase."""
    lines = ["## Sync with Remote\n"]

    try:
        # Use pull --rebase --autostash to preserve local changes
        result = subprocess.run(
            ["git", "-c", "safe.directory=/project", "pull", "--rebase", "--autostash"],
            capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT)
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            if "Already up to date" in output or "Already up-to-date" in output:
                lines.append("**Status:** Already up to date")
            else:
                lines.append("**Status:** Synced successfully")
                if output:
                    lines.append(f"**Details:**\n```\n{output[:500]}\n```")
        else:
            error = result.stderr.strip()
            if "CONFLICT" in error:
                lines.append("**Status:** CONFLICT detected")
                lines.append("**Action Required:** Resolve conflicts manually")
            else:
                lines.append(f"**Status:** FAILED")
                lines.append(f"**Error:**\n```\n{error[:500]}\n```")

    except subprocess.TimeoutExpired:
        lines.append("**Status:** TIMEOUT (network issue or large fetch)")
    except Exception as e:
        lines.append(f"**Status:** ERROR - {e}")

    return "\n".join(lines)


def get_agent_policy(chat_id: int = 0) -> str:
    if not chat_id:
        return "Agent policy is unavailable: missing chat context."

    policy = load_agent_policy(chat_id)
    return format_agent_policy(policy)


def self_update_policy(
    action: str,
    reason: str,
    chat_id: int = 0,
    rules: list[str] | None = None,
    focus: list[str] | None = None,
) -> str:
    if not chat_id:
        return "Self-update unavailable: missing chat context."

    try:
        updated = apply_agent_policy_update(
            chat_id=chat_id,
            action=action,
            rules=rules,
            focus=focus,
            reason=reason,
        )
    except ValueError as e:
        return f"Invalid self-update action: {e}"
    except Exception as e:
        return f"Self-update failed: {e}"

    return "Self-update applied.\n\n" + format_agent_policy(updated)


# --- Fact checker ---

def _extract_keywords(claim: str) -> list[str]:
    """Extract meaningful keywords from a claim for searching."""
    stop_words = {
        "i", "me", "my", "we", "our", "you", "your", "the", "a", "an", "is",
        "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "will", "would", "could", "should", "may",
        "might", "shall", "can", "to", "of", "in", "for", "on", "with",
        "at", "by", "from", "as", "into", "about", "that", "this", "it",
        "not", "no", "but", "or", "and", "if", "then", "so", "than",
        "said", "told", "going", "want", "think", "know",
    }
    words = re.findall(r"[a-zA-Z0-9]+", claim.lower())
    return [w for w in words if w not in stop_words and len(w) > 2]


def _search_memory(keywords: list[str]) -> list[dict]:
    """Search approved_memory table for keyword matches."""
    evidence = []
    services = get_services()
    try:
        with services.store._connect() as conn:
            rows = conn.execute(
                """
                SELECT kind, subject_key, payload_json
                FROM approved_memory
                WHERE active = 1
                """,
            ).fetchall()
    except Exception:
        return evidence

    for row in rows:
        payload_str = row["payload_json"] or ""
        search_text = f"{row['kind']} {row['subject_key']} {payload_str}".lower()
        matching_keywords = [kw for kw in keywords if kw in search_text]
        if matching_keywords:
            payload = json.loads(payload_str) if payload_str else {}
            evidence.append({
                "source": f"approved_memory ({row['kind']})",
                "matched_keywords": matching_keywords,
                "summary": f"[{row['kind']}] {payload}",
            })
    return evidence


def _search_logs_for_claim(keywords: list[str], days: int) -> list[dict]:
    """Search daily logs for evidence related to keywords."""
    evidence = []
    logs_dir = REPO_ROOT / "content" / "logs"
    if not logs_dir.exists():
        return evidence

    cutoff = datetime.now() - timedelta(days=days)

    for log_file in sorted(logs_dir.glob("*.md"), reverse=True):
        try:
            date_str = log_file.stem
            log_date = datetime.strptime(date_str, "%Y-%m-%d")
            if log_date < cutoff:
                break
        except ValueError:
            continue

        try:
            content = log_file.read_text()
        except OSError:
            continue

        content_lower = content.lower()
        matching_keywords = [kw for kw in keywords if kw in content_lower]
        if not matching_keywords:
            continue

        # Collect matching lines for context
        matching_lines = []
        for line in content.split("\n"):
            line_lower = line.lower()
            if any(kw in line_lower for kw in matching_keywords):
                stripped = line.strip()
                if stripped:
                    matching_lines.append(stripped)

        if matching_lines:
            evidence.append({
                "source": f"logs/{date_str}.md",
                "matched_keywords": matching_keywords,
                "summary": "; ".join(matching_lines[:5]),
            })

        if len(evidence) >= 10:
            break

    return evidence


def _search_history_for_claim(keywords: list[str], chat_id: int = 0) -> list[dict]:
    """Search conversation history via SQLite turn table."""
    evidence = []
    services = get_services()
    # Search for each keyword that has 3+ characters
    seen_turn_ids: set[str] = set()
    for kw in keywords[:5]:
        rows = services.store.search_turns(chat_id, kw, limit=10, days=30)
        for row in rows:
            turn_key = row.get("created_at_utc", "")
            if turn_key in seen_turn_ids:
                continue
            text = row["text"]
            text_lower = text.lower()
            matching_keywords = [k for k in keywords if k in text_lower]
            if len(matching_keywords) >= 2:
                seen_turn_ids.add(turn_key)
                preview = text[:300] + "..." if len(text) > 300 else text
                evidence.append({
                    "source": f"conversation ({row['role']})",
                    "matched_keywords": matching_keywords,
                    "summary": preview,
                })
                if len(evidence) >= 5:
                    return evidence
    return evidence


def fact_check(claim: str, sources: str = "all", days: int = 30, chat_id: int = 0) -> str:
    """Verify a claim against stored knowledge and return evidence report."""
    keywords = _extract_keywords(claim)
    if not keywords:
        return "Could not extract meaningful keywords from the claim. Please rephrase."

    source_list = [s.strip().lower() for s in sources.split(",")]
    check_all = "all" in source_list

    all_evidence = []

    # Search approved memory (SQLite)
    if check_all or "memory" in source_list:
        memory_evidence = _search_memory(keywords)
        all_evidence.extend(memory_evidence)

    # Search daily logs (file-based — logs are projections not in SQLite)
    if check_all or "logs" in source_list:
        log_evidence = _search_logs_for_claim(keywords, days)
        all_evidence.extend(log_evidence)

    # Search conversation history (SQLite turn table)
    if check_all or "history" in source_list:
        history_evidence = _search_history_for_claim(keywords, chat_id=chat_id)
        all_evidence.extend(history_evidence)

    # Build report
    lines = [f"## Fact Check Report\n"]
    lines.append(f"**Claim:** {claim}")
    lines.append(f"**Keywords:** {', '.join(keywords)}")
    lines.append(f"**Sources checked:** {sources}")
    lines.append(f"**Evidence found:** {len(all_evidence)} item(s)\n")

    if not all_evidence:
        lines.append("**Verdict: UNVERIFIED**")
        lines.append("No matching evidence found in the searched sources. "
                      "This doesn't mean the claim is false -- it may simply "
                      "not be recorded in the system.")
    else:
        lines.append("**Verdict: EVIDENCE FOUND** (review below)\n")
        lines.append("### Evidence\n")
        for i, ev in enumerate(all_evidence[:15], 1):
            lines.append(f"**{i}. [{ev['source']}]** (matched: {', '.join(ev['matched_keywords'])})")
            lines.append(f"   {ev['summary']}\n")

        lines.append("---")
        lines.append("*Note: This is keyword-based evidence retrieval. "
                      "Review the evidence above to determine if it supports "
                      "or contradicts the claim.*")

    return "\n".join(lines)


# --- Brain DB tools ---

def _get_brain_db():
    """Import brain_db lazily."""
    import brain_db
    return brain_db


def tool_semantic_search(query: str, doc_type: str = "", limit: int = 5) -> str:
    """Semantic + keyword search across the second brain."""
    try:
        brain = _get_brain_db()
        results = brain.semantic_search(
            query,
            doc_type=doc_type if doc_type else None,
            limit=limit,
        )

        if not results:
            return f"No results found for '{query}'."

        lines = [f"## Semantic Search: {len(results)} results\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            score = r.get("similarity", 0)
            match_type = r.get("match_type", "unknown")
            preview = r.get("chunk_text", "")[:300]
            lines.append(f"**{i}. [{r['doc_type']}] {title}** (score: {score:.2f}, {match_type})")
            lines.append(f"   Source: {r.get('source', 'unknown')}")
            lines.append(f"   {preview}\n")

        return "\n".join(lines)
    except Exception as e:
        return f"Semantic search error: {e}"


def tool_ingest_content(content: str, title: str = "", doc_type: str = "note") -> str:
    """Ingest content into the second brain."""
    try:
        brain = _get_brain_db()
        result = brain.ingest_document(
            content=content,
            doc_type=doc_type,
            title=title,
            source="bot_ingest",
        )
        return (
            f"Ingested into brain:\n"
            f"- Document ID: {result['doc_id']}\n"
            f"- Entities extracted: {result['entities']}\n"
            f"- Relationships found: {result['relationships']}\n"
            f"- Preferences detected: {result['preferences']}"
        )
    except Exception as e:
        return f"Ingestion error: {e}"


def tool_explore_connections(entity_name: str, hops: int = 1) -> str:
    """Explore entity connections in the knowledge graph."""
    try:
        brain = _get_brain_db()

        # Find the entity first
        entities = brain.find_entities(name=entity_name)
        if not entities:
            return f"No entity found matching '{entity_name}'."

        entity = entities[0]
        lines = [f"## Connections for: {entity['name']} ({entity['entity_type']})\n"]

        props = json.loads(entity.get("properties", "{}")) if isinstance(entity.get("properties"), str) else entity.get("properties", {})
        if props:
            lines.append("**Properties:**")
            for k, v in props.items():
                if v:
                    lines.append(f"  - {k}: {v}")
            lines.append("")

        connections = brain.get_connections(entity["id"], hops=min(hops, 2))
        if connections:
            lines.append(f"**Connected entities ({len(connections)}):**")
            for c in connections:
                hop_label = f"({c['hops']}-hop)" if c.get("hops", 1) > 1 else ""
                c_props = json.loads(c.get("properties", "{}")) if isinstance(c.get("properties"), str) else c.get("properties", {})
                detail = ""
                if c_props:
                    detail = " — " + ", ".join(f"{k}={v}" for k, v in c_props.items() if v)
                lines.append(f"  - {c['name']} [{c['entity_type']}] via {c['relationship_type']} {hop_label}{detail}")
        else:
            lines.append("No connections found.")

        return "\n".join(lines)
    except Exception as e:
        return f"Connection exploration error: {e}"


def tool_brain_stats() -> str:
    """Get brain DB statistics."""
    try:
        brain = _get_brain_db()
        stats = brain.get_brain_stats()

        lines = ["## Second Brain Stats\n"]
        for table, count in stats.items():
            lines.append(f"- {table}: {count}")

        return "\n".join(lines)
    except Exception as e:
        return f"Brain stats error: {e}"


# --- Nutrition tools ---

def tool_run_query(db: str, sql: str) -> str:
    services = get_services()
    result = services.analytics.run_query(db, sql)
    if "error" in result:
        return f"Query error: {result['error']}"
    return json.dumps(result, default=str)


def tool_metric_trend(chat_id: int, field: str, days: int = 30) -> str:
    services = get_services()
    result = services.analytics.metric_trend(chat_id, field, days)
    return json.dumps(result, default=str)


def tool_habit_completion(chat_id: int, habit_name: str, days: int = 30) -> str:
    services = get_services()
    result = services.analytics.habit_completion(chat_id, habit_name, days)
    return json.dumps(result, default=str)


def tool_nutrition_summary(chat_id: int, date: str | None = None, days: int = 7) -> str:
    services = get_services()
    result = services.analytics.nutrition_summary(chat_id, date, days)
    return json.dumps(result, default=str)


def tool_correlate(chat_id: int, field_a: str, field_b: str, days: int = 30) -> str:
    services = get_services()
    result = services.analytics.correlate(chat_id, field_a, field_b, days)
    return json.dumps(result, default=str)


def tool_get_computed_insights(chat_id: int) -> str:
    services = get_services()
    result = services.analytics.get_computed_insights(chat_id)
    return json.dumps(result, default=str)


# --- Daily Todo Tool Handlers ---


def _compact_todo_summary(chat_id: int, local_date: str) -> str:
    """Return a one-line todo summary like 'Todos: 3/7 done (2 must_win, 1 can_do open)'."""
    services = get_services()
    todos = services.store.list_daily_todos(chat_id, local_date)
    if not todos:
        return "Todos: none"
    total = len(todos)
    done = sum(1 for t in todos if t["status"] == "completed")
    open_todos = [t for t in todos if t["status"] not in ("completed", "cancelled")]
    open_cats = {}
    for t in open_todos:
        cat = t.get("category") or "uncategorized"
        open_cats[cat] = open_cats.get(cat, 0) + 1
    open_detail = ", ".join(f"{v} {k}" for k, v in open_cats.items()) if open_cats else "none"
    return f"Todos: {done}/{total} done (open: {open_detail})"


def tool_create_todo(chat_id: int, title: str, category: str = "", date: str | None = None, is_top3: bool = False) -> str:
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    result = services.store.create_daily_todo(
        chat_id, local_date, title, category=category, source="manual", is_top3=is_top3,
    )
    top3_label = " [priority]" if is_top3 else ""
    cat_label = f" ({category})" if category else ""
    summary = _compact_todo_summary(chat_id, local_date)
    return f"Created todo{top3_label}{cat_label}: {result['title']} for {local_date}\n{summary}"


def tool_complete_todo(chat_id: int, todo_id_or_title: str) -> str:
    services = get_services()
    result = services.store.complete_open_loop(chat_id, todo_id_or_title)
    if not result:
        return f"Todo not found: {todo_id_or_title}"
    local_date = _resolve_local_date(chat_id, None)
    summary = _compact_todo_summary(chat_id, local_date)
    return f"Completed: {result['title']}\n{summary}"


def tool_drop_todo(chat_id: int, todo_id_or_title: str, notes: str = "") -> str:
    services = get_services()
    with services.store.begin_write() as conn:
        row = conn.execute(
            """
            SELECT loop_id, title FROM open_loop
            WHERE chat_id = ? AND kind = 'daily_todo'
              AND (loop_id = ? OR LOWER(title) = LOWER(?))
            ORDER BY created_at_utc DESC LIMIT 1
            """,
            (chat_id, todo_id_or_title, todo_id_or_title),
        ).fetchone()
        if not row:
            return f"Todo not found: {todo_id_or_title}"
        updates = "status = 'cancelled'"
        params: list = []
        if notes:
            updates += ", notes = ?"
            params.append(notes)
        params.append(row["loop_id"])
        conn.execute(f"UPDATE open_loop SET {updates} WHERE loop_id = ?", params)
    local_date = _resolve_local_date(chat_id, None)
    summary = _compact_todo_summary(chat_id, local_date)
    return f"Dropped: {row['title']}" + (f" ({notes})" if notes else "") + f"\n{summary}"


def tool_defer_todo(chat_id: int, todo_id_or_title: str, to_date: str) -> str:
    services = get_services()
    with services.store.begin_write() as conn:
        row = conn.execute(
            """
            SELECT loop_id, title FROM open_loop
            WHERE chat_id = ? AND kind = 'daily_todo' AND status = 'open'
              AND (loop_id = ? OR LOWER(title) = LOWER(?))
            ORDER BY created_at_utc DESC LIMIT 1
            """,
            (chat_id, todo_id_or_title, todo_id_or_title),
        ).fetchone()
        if not row:
            return f"Open todo not found: {todo_id_or_title}"
        # Mark current as rolled
        conn.execute("UPDATE open_loop SET status = 'rolled' WHERE loop_id = ?", (row["loop_id"],))
    # Create new todo on target date
    services.store.create_daily_todo(chat_id, to_date, row["title"], source="rollover")
    return f"Deferred '{row['title']}' to {to_date}"


def tool_list_todos(chat_id: int, date: str | None = None, status: str | None = None) -> str:
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    todos = services.store.list_daily_todos(chat_id, local_date, status=status)
    if not todos:
        return f"No todos for {local_date}" + (f" (status={status})" if status else "") + "."
    lines = [f"**Todos for {local_date}:**"]
    for t in todos:
        mark = "[x]" if t["status"] == "completed" else "[-]" if t["status"] == "cancelled" else "[ ]"
        cat = f" ({t['category']})" if t.get("category") else ""
        rolled = f" [rolled {t['rollover_count']}x]" if int(t.get("rollover_count", 0)) > 0 else ""
        top3 = " *" if t.get("is_top3") else ""
        lines.append(f"- {mark} {t['title']}{cat}{rolled}{top3}")
    total = len(todos)
    done = sum(1 for t in todos if t["status"] == "completed")
    lines.append(f"\n{done}/{total} completed")
    return "\n".join(lines)


def tool_set_priorities(chat_id: int, items: list[str], date: str | None = None) -> str:
    services = get_services()
    if not date:
        # Default to tomorrow
        from datetime import timedelta
        resolved = services.resolver.resolve_now(chat_id)
        tomorrow = (resolved.local_now + timedelta(days=1)).strftime("%Y-%m-%d")
        local_date = tomorrow
    else:
        local_date = date
    # Ensure the target day exists
    services.store.ensure_day_open(services.resolver.resolve_now(chat_id))
    created = []
    for title in items:
        result = services.store.create_daily_todo(
            chat_id, local_date, title, category="must_win", source="top3", is_top3=True,
        )
        created.append(result["title"])
    return f"Set {len(created)} priorities for {local_date}:\n" + "\n".join(f"- {t}" for t in created)


# --- Agent-Parity Tool Handlers ---


def tool_close_day(chat_id: int, date: str | None = None) -> str:
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    result = services.store.close_day(chat_id, local_date)
    if result:
        return f"Day {local_date} closed."
    return f"Could not close day {local_date} (may already be closed or not exist)."


def tool_snooze_loop(chat_id: int, loop_id_or_title: str, minutes: int = 60) -> str:
    services = get_services()
    result = services.store.snooze_open_loop(chat_id, loop_id_or_title, minutes)
    if not result:
        return f"Open loop not found: {loop_id_or_title}"
    return f"Snoozed '{result['title']}' until {result['snoozed_until_utc']}"


def tool_manage_habit(chat_id: int, action: str, name: str, new_name: str = "", cadence: str = "daily") -> str:
    services = get_services()
    if action == "create":
        result = services.store.create_habit_definition(chat_id, name, cadence)
        return f"Created habit: {result['name']} (cadence: {result['cadence']})"
    elif action == "disable":
        result = services.store.update_habit_definition(chat_id, name, active=False)
        if not result:
            return f"Habit not found: {name}"
        return f"Disabled habit: {result['name']}"
    elif action == "enable":
        result = services.store.update_habit_definition(chat_id, name, active=True)
        if not result:
            return f"Habit not found: {name}"
        return f"Enabled habit: {result['name']}"
    elif action == "rename":
        if not new_name:
            return "new_name is required for rename action."
        result = services.store.update_habit_definition(chat_id, name, name=new_name)
        if not result:
            return f"Habit not found: {name}"
        return f"Renamed habit to: {result['name']}"
    return f"Unknown action: {action}"


def tool_save_reflection(chat_id: int, went_well: str = "", went_poorly: str = "", lessons: str = "", date: str | None = None) -> str:
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    result = services.store.save_reflection(chat_id, local_date, went_well=went_well, went_poorly=went_poorly, lessons=lessons)
    if not result:
        return f"Could not save reflection for {local_date} (day may not exist)."
    parts = []
    if went_well:
        parts.append(f"Went well: {went_well[:80]}")
    if went_poorly:
        parts.append(f"Went poorly: {went_poorly[:80]}")
    if lessons:
        parts.append(f"Lessons: {lessons[:80]}")
    return f"Reflection saved for {local_date}.\n" + "\n".join(parts)


def tool_get_reflections(chat_id: int, date: str | None = None) -> str:
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    ref = services.store.get_reflection(chat_id, local_date)
    if not any(ref.values()):
        return f"No reflections recorded for {local_date}."
    lines = [f"**Reflections for {local_date}:**"]
    if ref["went_well"]:
        lines.append(f"**What Went Well:** {ref['went_well']}")
    if ref["went_poorly"]:
        lines.append(f"**What Went Poorly:** {ref['went_poorly']}")
    if ref["lessons"]:
        lines.append(f"**Lessons:** {ref['lessons']}")
    return "\n".join(lines)


def tool_mute_coaching(chat_id: int, minutes: int = 60) -> str:
    try:
        from bot import _coaching_heartbeat
        if _coaching_heartbeat:
            _coaching_heartbeat.mute(minutes)
            return f"Coaching muted for {minutes} minutes."
        return "Coaching heartbeat not available."
    except Exception as e:
        return f"Could not mute coaching: {e}"


def tool_unmute_coaching(chat_id: int) -> str:
    try:
        from bot import _coaching_heartbeat
        if _coaching_heartbeat:
            _coaching_heartbeat.unmute()
            return "Coaching unmuted."
        return "Coaching heartbeat not available."
    except Exception as e:
        return f"Could not unmute coaching: {e}"


def tool_get_token_usage(chat_id: int) -> str:
    try:
        from claude_client import ConversationState, DAILY_TOKEN_BUDGET, get_model_pricing
        state = ConversationState.load_from_disk(chat_id)
        pricing = get_model_pricing()
        total_tokens = state.total_input_tokens + state.total_output_tokens
        daily_tokens = state.daily_input_tokens + state.daily_output_tokens
        budget_pct = round(daily_tokens / DAILY_TOKEN_BUDGET * 100, 1) if DAILY_TOKEN_BUDGET else 0
        est_cost = (
            state.total_input_tokens * pricing["input_per_token"]
            + state.total_output_tokens * pricing["output_per_token"]
        )
        lines = [
            "**Token Usage:**",
            f"  Daily: {daily_tokens:,} / {DAILY_TOKEN_BUDGET:,} ({budget_pct}%)",
            f"  Total: {total_tokens:,}",
            f"  Estimated cost: ${est_cost:.4f}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Token usage unavailable: {e}"


def _get_nutrition_totals_from_sqlite(chat_id: int, local_date: str) -> dict[str, Any]:
    """Get running nutrition totals from SQLite food_entry table."""
    services = get_services()
    snapshot = services.store.get_day_snapshot(chat_id, local_date)
    if not snapshot or not snapshot.foods:
        return {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fiber_g": 0, "count": 0}
    totals = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fiber_g": 0, "count": len(snapshot.foods)}
    for food in snapshot.foods:
        totals["calories"] += int(food.get("calories_est") or 0)
        totals["protein_g"] += int(food.get("protein_g_est") or 0)
        totals["carbs_g"] += int(food.get("carbs_g_est") or 0)
        totals["fat_g"] += int(food.get("fat_g_est") or 0)
        totals["fiber_g"] += int(food.get("fiber_g_est") or 0)
    return totals


def tool_log_food(food_description: str, chat_id: int = 0) -> str:
    """Estimate macros for food, write to SQLite, return estimate + running totals."""
    try:
        from calorie_estimator import estimate_food
    except ImportError as e:
        return f"Calorie estimator unavailable: {e}"

    result = estimate_food(food_description)
    if not result.get("success"):
        return f"Estimation failed: {result.get('error', 'Unknown error')}"

    # Write macros to SQLite food_entry (single source of truth)
    local_date = _resolve_local_date(chat_id, None) if chat_id else datetime.now().strftime("%Y-%m-%d")
    if chat_id:
        services = get_services()
        services.store.append_food(
            chat_id, local_date, food_description,
            calories_est=result.get("calories"),
            protein_g_est=result.get("protein_g"),
            carbs_g_est=result.get("carbs_g"),
            fat_g_est=result.get("fat_g"),
            fiber_g_est=result.get("fiber_g"),
        )

    lines = [
        f"**Logged:** {food_description}",
        f"  Calories: {result['calories']} | Protein: {result['protein_g']}g | Carbs: {result['carbs_g']}g | Fat: {result['fat_g']}g | Fiber: {result.get('fiber_g', 0)}g",
    ]

    if result.get("line_items"):
        lines.append("  Breakdown:")
        for item in result["line_items"]:
            lines.append(f"    - {item}")

    # Get running totals from SQLite
    if chat_id:
        totals = _get_nutrition_totals_from_sqlite(chat_id, local_date)
        lines.append("")
        lines.append(f"**Daily totals:** {totals['calories']} cal | {totals['protein_g']}g protein | {totals['carbs_g']}g carbs | {totals['fat_g']}g fat | {totals['fiber_g']}g fiber")
        lines.append(f"  Entries today: {totals['count']}")

    return "\n".join(lines)


def tool_log_workout(
    chat_id: int,
    workout_type: str,
    exercises: list[dict] | None = None,
    cardio: list[dict] | None = None,
    notes: str = "",
    date: str | None = None,
) -> str:
    """Log a workout session to SQLite."""
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    result = services.store.record_workout(
        chat_id=chat_id,
        local_date=local_date,
        workout_type=workout_type,
        exercises=exercises,
        cardio=cardio,
        notes=notes,
    )
    parts = [f"Logged {workout_type} workout for {local_date}"]
    if result["exercises"]:
        parts.append(f"  {result['exercises']} exercise(s)")
    if result["cardio_activities"]:
        parts.append(f"  {result['cardio_activities']} cardio activity/ies")
    return "\n".join(parts)


def tool_get_nutrition_totals(date: str = None, chat_id: int = 0) -> str:
    """Get running nutrition totals for a given day from SQLite."""
    label = date if date else datetime.now().strftime("%Y-%m-%d")
    local_date = _resolve_local_date(chat_id, date) if chat_id else label

    totals = _get_nutrition_totals_from_sqlite(chat_id, local_date) if chat_id else {
        "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fiber_g": 0, "count": 0,
    }

    lines = [
        f"**Nutrition totals for {label}:**",
        f"  Calories: {totals['calories']}",
        f"  Protein: {totals['protein_g']}g",
        f"  Carbs: {totals['carbs_g']}g",
        f"  Fat: {totals['fat_g']}g",
        f"  Fiber: {totals['fiber_g']}g",
        f"  Entries: {totals['count']}",
    ]

    return "\n".join(lines)



def tool_decompose_goal(chat_id: int, goal: str, subtasks: list[str]) -> str:
    services = get_services()
    resolved = services.timezone_resolver.resolve_now(chat_id)
    day = services.store.ensure_day_open(resolved)
    # Create parent goal
    parent = services.store.create_open_loop(
        chat_id=chat_id, title=goal, kind="task", priority="high",
        due_at_utc="", day_id=day["day_id"],
    )
    # Create child sub-tasks linked to parent
    children = []
    for sub in subtasks:
        child = services.store.create_open_loop(
            chat_id=chat_id, title=sub, kind="task", priority="normal",
            due_at_utc="", day_id=day["day_id"],
        )
        # Link child to parent
        with services.store.begin_write() as conn:
            conn.execute(
                "UPDATE open_loop SET parent_loop_id = ? WHERE loop_id = ?",
                (parent["loop_id"], child["loop_id"]),
            )
        children.append(child)
    services.projection.render_private_day_log(day["day_id"])
    lines = [f"Goal: {goal} [{parent['loop_id']}]", f"Sub-tasks ({len(children)}):"]
    for c in children:
        lines.append(f"  - {c['title']} [{c['loop_id']}]")
    return "\n".join(lines)


def tool_goal_progress(chat_id: int, goal_id_or_title: str) -> str:
    services = get_services()
    # Find the parent goal
    with services.store._connect() as conn:
        parent = conn.execute(
            "SELECT loop_id, title, status FROM open_loop WHERE chat_id = ? AND (loop_id = ? OR LOWER(title) = LOWER(?)) LIMIT 1",
            (chat_id, goal_id_or_title, goal_id_or_title),
        ).fetchone()
        if not parent:
            return f"Goal not found: {goal_id_or_title}"
        children = conn.execute(
            "SELECT loop_id, title, status FROM open_loop WHERE parent_loop_id = ? ORDER BY created_at_utc",
            (parent["loop_id"],),
        ).fetchall()
    if not children:
        return f"Goal: {parent['title']} [{parent['status']}] (no sub-tasks)"
    done = sum(1 for c in children if c["status"] == "completed")
    total = len(children)
    pct = int(done / total * 100) if total > 0 else 0
    lines = [f"Goal: {parent['title']} — {pct}% ({done}/{total} sub-tasks done)"]
    for c in children:
        mark = "✓" if c["status"] == "completed" else "✗"
        lines.append(f"  {mark} {c['title']}")
    return "\n".join(lines)


def tool_refresh_context(chat_id: int) -> str:
    return get_day_snapshot(chat_id, None)


def tool_self_reflect(chat_id: int, observation: str) -> str:
    import uuid
    services = get_services()
    reflection_id = str(uuid.uuid4())[:8]
    with services.store.begin_write() as conn:
        conn.execute(
            "INSERT INTO agent_reflection (reflection_id, chat_id, observation, created_at_utc) VALUES (?, ?, ?, ?)",
            (reflection_id, chat_id, observation, services.clock.now_utc().isoformat()),
        )
    return f"Reflection recorded [{reflection_id}]: {observation[:80]}..."


async def execute_tool(name: str, inputs: dict, chat_id: int = 0) -> str:
    try:
        return _dispatch_tool(name, inputs, chat_id)
    except Exception as e:
        return f"Tool error ({name}): {e}"


def _dispatch_tool(name: str, inputs: dict, chat_id: int) -> str:
    if name == "think":
        thought = inputs.get("thought")
        if not thought:
            return "[think tool called with no thought content]"
        return "Thinking recorded."
    if name == "list_extended_tools":
        return get_extended_tool_descriptions()
    if name == "get_day_snapshot":
        return get_day_snapshot(chat_id, inputs.get("date"))
    if name == "set_timezone":
        return set_timezone(chat_id, inputs["timezone"], inputs.get("location_label"))
    if name == "update_day_metric":
        return update_day_metric(chat_id, inputs["field"], inputs["value"], inputs.get("date"))
    if name == "append_food":  # backward compat -> route to log_food
        return tool_log_food(inputs.get("description", inputs.get("food_description", "")), chat_id=chat_id)
    if name == "mark_habit":
        return mark_habit(chat_id, inputs["habit_id"], inputs["status"], inputs.get("date"))
    if name == "create_open_loop":
        return create_open_loop(
            chat_id,
            inputs["title"],
            inputs["kind"],
            priority=inputs.get("priority", "normal"),
            due_hours=inputs.get("due_hours"),
        )
    if name == "complete_open_loop":
        return complete_open_loop(chat_id, inputs["loop_id_or_title"])
    if name == "list_due_followups":
        return list_due_followups(chat_id)
    if name == "list_stale_loops":
        age = inputs.get("age_days", 3)
        services = get_services()
        loops = services.store.list_stale_loops(chat_id, age_days=age)
        if not loops:
            return f"No open loops older than {age} days."
        lines = [f"Zombie tasks (>{age} days old):"]
        for loop in loops:
            age_d = loop.get("age_days", "?")
            rolled = loop.get("rollover_count", 0)
            lines.append(f"- [{loop['priority']}] {loop['title']} ({age_d}d old, rolled {rolled}x) [id: {loop['loop_id']}]")
        return "\n".join(lines)
    if name == "create_intervention":
        services = get_services()
        target = inputs["target_metric"]
        baseline = None
        sample = 0
        try:
            trend = services.analytics.metric_trend(chat_id, target, days=7)
            if trend and trend.get("mean") is not None:
                baseline = trend["mean"]
                sample = trend.get("sample_size", 0)
        except Exception:
            pass
        result = services.store.create_intervention(
            chat_id,
            strategy_text=inputs["strategy"],
            target_metric=target,
            duration_days=inputs.get("duration_days", 7),
            baseline_value=baseline,
            baseline_sample_size=sample,
        )
        baseline_str = f"{baseline:.1f}" if baseline is not None else "no data"
        return (
            f"Intervention started: \"{result['strategy_text']}\"\n"
            f"Target: {result['target_metric']} (baseline: {baseline_str}, {sample} data points)\n"
            f"Evaluation date: {result['evaluation_date']}"
        )
    if name == "evaluate_intervention":
        services = get_services()
        intv_id = inputs["intervention_id"]
        interventions = services.store.list_interventions(chat_id)
        target_intv = next((i for i in interventions if i["intervention_id"] == intv_id), None)
        if not target_intv:
            return f"Intervention not found: {intv_id}"
        current = None
        try:
            trend = services.analytics.metric_trend(chat_id, target_intv["target_metric"], days=7)
            if trend:
                current = trend.get("mean")
        except Exception:
            pass
        result = services.store.evaluate_intervention(chat_id, intv_id, current_value=current)
        if not result:
            return f"Could not evaluate intervention: {intv_id}"
        return f"Evaluation: {result['outcome_text']}"
    if name == "list_interventions":
        services = get_services()
        status = inputs.get("status")
        interventions = services.store.list_interventions(chat_id, status=status)
        if not interventions:
            return "No interventions found."
        lines = ["Interventions:"]
        for intv in interventions:
            baseline_str = f"{intv['baseline_value']:.1f}" if intv.get("baseline_value") is not None else "?"
            lines.append(
                f"- [{intv['status']}] \"{intv['strategy_text']}\" -> {intv['target_metric']} "
                f"(baseline: {baseline_str}, eval: {intv['evaluation_date']}) [id: {intv['intervention_id']}]"
            )
        return "\n".join(lines)
    # --- manage_memory (merged: queue_memory_candidates + review_memory_candidate) ---
    if name == "manage_memory":
        action = inputs["action"]
        if action == "queue":
            return queue_memory_candidates(chat_id, inputs["text"])
        if action in ("approve", "reject"):
            return review_memory_candidate(chat_id, inputs["candidate_id"], action)
        return f"Unknown manage_memory action: {action}"
    if name == "queue_memory_candidates":  # backward compat
        return queue_memory_candidates(chat_id, inputs["text"])
    if name == "review_memory_candidate":  # backward compat
        return review_memory_candidate(chat_id, inputs["candidate_id"], inputs["action"])
    # --- Ported v1 tool dispatch ---
    if name == "read_file":
        return read_file(inputs["path"])
    if name == "write_file":
        return write_file(inputs["path"], inputs["content"])
    if name == "list_files":
        return list_files(inputs["path"], inputs.get("pattern", "*"))
    if name == "grep_files":
        return grep_files(inputs["pattern"], inputs.get("path", "."), inputs.get("file_glob", "*.md"))
    if name == "run_daily_planner":
        return run_daily_planner()
    if name == "run_weekly_planner":
        return run_weekly_planner(this_week=inputs.get("this_week", False))
    if name == "get_brain_status":
        return get_brain_status(chat_id=chat_id)
    if name == "capture_to_inbox":
        return capture_to_inbox(inputs["text"])
    if name == "search_logs":
        return search_logs(inputs["query"], inputs.get("days", 30))
    if name == "manage_cron":
        return manage_cron(inputs["action"], inputs.get("schedule"), inputs.get("command_name"))
    if name == "run_script":
        return run_script(inputs["script_name"], inputs.get("args", ""))
    if name == "search_conversation_history":
        return search_conversation_history(inputs["query"], inputs.get("limit", 20), chat_id=chat_id)
    if name == "get_system_status":
        return get_system_status()
    if name == "get_current_datetime":
        return get_current_datetime()
    if name == "check_git_health":
        return check_git_health()
    if name == "sync_with_remote":
        return sync_with_remote()
    # --- manage_policy (merged: get_agent_policy + self_update_policy) ---
    if name == "manage_policy":
        action = inputs["action"]
        if action == "get":
            return get_agent_policy(chat_id=chat_id)
        return self_update_policy(
            action=action,
            reason=inputs.get("reason", ""),
            chat_id=chat_id,
            rules=inputs.get("rules"),
            focus=inputs.get("focus"),
        )
    if name == "get_agent_policy":  # backward compat
        return get_agent_policy(chat_id=chat_id)
    if name == "self_update_policy":  # backward compat
        return self_update_policy(
            action=inputs["action"],
            reason=inputs["reason"],
            chat_id=chat_id,
            rules=inputs.get("rules"),
            focus=inputs.get("focus"),
        )
    if name == "fact_check":
        return fact_check(inputs["claim"], inputs.get("sources", "all"), inputs.get("days", 30), chat_id=chat_id)
    if name == "semantic_search":
        return tool_semantic_search(inputs["query"], inputs.get("doc_type", ""), inputs.get("limit", 5))
    if name == "ingest_content":
        return tool_ingest_content(inputs["content"], inputs.get("title", ""), inputs.get("doc_type", "note"))
    if name == "explore_connections":
        return tool_explore_connections(inputs["entity_name"], inputs.get("hops", 1))
    if name == "brain_stats":
        return tool_brain_stats()
    if name == "run_query":
        return tool_run_query(inputs["db"], inputs["sql"])
    # --- analyze_metrics (merged: metric_trend + correlate + get_computed_insights) ---
    if name == "analyze_metrics":
        analysis_type = inputs["analysis_type"]
        if analysis_type == "trend":
            return tool_metric_trend(chat_id, inputs["field"], inputs.get("days", 30))
        if analysis_type == "correlation":
            return tool_correlate(chat_id, inputs["field_a"], inputs["field_b"], inputs.get("days", 30))
        if analysis_type == "insights":
            return tool_get_computed_insights(chat_id)
        return f"Unknown analysis_type: {analysis_type}"
    if name == "metric_trend":  # backward compat
        return tool_metric_trend(chat_id, inputs["field"], inputs.get("days", 30))
    if name == "correlate":  # backward compat
        return tool_correlate(chat_id, inputs["field_a"], inputs["field_b"], inputs.get("days", 30))
    if name == "get_computed_insights":  # backward compat
        return tool_get_computed_insights(chat_id)
    if name == "habit_completion":
        return tool_habit_completion(chat_id, inputs["habit_name"], inputs.get("days", 30))
    # --- get_nutrition_summary (merged: get_nutrition_totals + nutrition_summary) ---
    if name in ("get_nutrition_summary", "nutrition_summary", "get_nutrition_totals"):
        return tool_nutrition_summary(chat_id, inputs.get("date"), inputs.get("days", 7))
    if name == "log_food":
        return tool_log_food(inputs["food_description"], chat_id=chat_id)
    if name == "log_workout":
        return tool_log_workout(
            chat_id=chat_id,
            workout_type=inputs["workout_type"],
            exercises=inputs.get("exercises"),
            cardio=inputs.get("cardio"),
            notes=inputs.get("notes", ""),
            date=inputs.get("date"),
        )
    # --- Daily Todo Tools ---
    if name == "create_todo":
        return tool_create_todo(chat_id, inputs["title"], category=inputs.get("category", ""), date=inputs.get("date"), is_top3=inputs.get("is_top3", False))
    # --- update_todo (merged: complete_todo + drop_todo) ---
    if name == "update_todo":
        action = inputs["action"]
        if action == "complete":
            return tool_complete_todo(chat_id, inputs["todo_id_or_title"])
        if action == "drop":
            return tool_drop_todo(chat_id, inputs["todo_id_or_title"], notes=inputs.get("notes", ""))
        return f"Unknown update_todo action: {action}"
    if name == "complete_todo":  # backward compat
        return tool_complete_todo(chat_id, inputs["todo_id_or_title"])
    if name == "drop_todo":  # backward compat
        return tool_drop_todo(chat_id, inputs["todo_id_or_title"], notes=inputs.get("notes", ""))
    if name == "defer_todo":
        return tool_defer_todo(chat_id, inputs["todo_id_or_title"], inputs["to_date"])
    if name == "list_todos":
        return tool_list_todos(chat_id, date=inputs.get("date"), status=inputs.get("status"))
    if name == "set_priorities":
        return tool_set_priorities(chat_id, inputs["items"], date=inputs.get("date"))
    # --- Agent-Parity Tools ---
    if name == "close_day":
        return tool_close_day(chat_id, date=inputs.get("date"))
    if name == "snooze_loop":
        return tool_snooze_loop(chat_id, inputs["loop_id_or_title"], minutes=inputs.get("minutes", 60))
    if name == "manage_habit":
        return tool_manage_habit(chat_id, inputs["action"], inputs["name"], new_name=inputs.get("new_name", ""), cadence=inputs.get("cadence", "daily"))
    if name == "save_reflection":
        return tool_save_reflection(chat_id, went_well=inputs.get("went_well", ""), went_poorly=inputs.get("went_poorly", ""), lessons=inputs.get("lessons", ""), date=inputs.get("date"))
    if name == "get_reflections":
        return tool_get_reflections(chat_id, date=inputs.get("date"))
    # --- manage_coaching (merged: mute_coaching + unmute_coaching) ---
    if name == "manage_coaching":
        action = inputs["action"]
        if action == "mute":
            return tool_mute_coaching(chat_id, minutes=inputs.get("minutes", 60))
        if action == "unmute":
            return tool_unmute_coaching(chat_id)
        return f"Unknown manage_coaching action: {action}"
    if name == "mute_coaching":  # backward compat
        return tool_mute_coaching(chat_id, minutes=inputs.get("minutes", 60))
    if name == "unmute_coaching":  # backward compat
        return tool_unmute_coaching(chat_id)
    if name == "get_token_usage":
        return tool_get_token_usage(chat_id)
    if name == "decompose_goal":
        return tool_decompose_goal(chat_id, inputs["goal"], inputs["subtasks"])
    if name == "goal_progress":
        return tool_goal_progress(chat_id, inputs["goal_id_or_title"])
    if name == "refresh_context":
        return tool_refresh_context(chat_id)
    if name == "self_reflect":
        return tool_self_reflect(chat_id, inputs["observation"])
    return f"Unknown V2 tool: {name}"
