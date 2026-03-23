"""
Background scheduler for cron-like jobs.

Replaces system cron with a Python-native scheduler that runs in a background thread.
Loads job configuration from the same cron_jobs.json used by the manage_cron tool.
"""

import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path

import requests
import schedule
from v2.bootstrap import get_services

logger = logging.getLogger(__name__)

# Use same HISTORY_DIR as tools.py and claude_client.py
PRIVATE_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))
CRON_CONFIG = PRIVATE_DIR / "cron_jobs.json"
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).parent.parent))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", "0") or 0)

# Map job names to their actual implementations
JOB_COMMANDS = {
    "morning_briefing": ["python", "scripts/send_routine_reminder.py", "morning"],
    "evening_reminder": ["python", "scripts/send_routine_reminder.py", "evening_start"],
    "evening_screens": ["python", "scripts/send_routine_reminder.py", "evening_screens"],
    "evening_bed": ["python", "scripts/send_routine_reminder.py", "evening_bed"],
    "daily_planner": ["python", "scripts/daily_planner.py"],
    "auto_backup": ["bash", "scripts/auto_backup.sh"],
    "brain_pattern_detection": None,  # Handled in-process, not via subprocess
    "weekly_planner": ["python", "scripts/weekly_planner.py", "--this-week"],
}

DOW_MAP = {
    "0": "sunday", "7": "sunday",
    "1": "monday", "2": "tuesday", "3": "wednesday",
    "4": "thursday", "5": "friday", "6": "saturday",
}
_last_v2_housekeeping = 0.0


def _send_v2_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not OWNER_CHAT_ID:
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": OWNER_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        logger.exception("Failed to send V2 reminder")
        return False


def _run_v2_housekeeping():
    if not OWNER_CHAT_ID:
        return
    services = get_services()
    resolved = services.timezone_resolver.resolve_now(OWNER_CHAT_ID)
    day = services.store.ensure_day_open(resolved)
    services.projection.render_private_day_log(day["day_id"])

    # Auto-evaluate due interventions
    try:
        due = services.store.list_due_evaluations(OWNER_CHAT_ID, as_of_date=resolved.local_date)
        for intv in due:
            current = None
            try:
                trend = services.analytics.metric_trend(OWNER_CHAT_ID, intv["target_metric"], days=7)
                if trend:
                    current = trend.get("mean")
            except Exception:
                pass
            services.store.evaluate_intervention(OWNER_CHAT_ID, intv["intervention_id"], current_value=current)
            logger.info("Auto-evaluated intervention: %s", intv["intervention_id"])
    except Exception:
        logger.exception("Failed to auto-evaluate interventions")

    # Reminder delivery disabled — coaching heartbeat handles proactive messaging.
    # SimpleReminderPolicy is still available as a data source for the coaching fallback.


def _run_brain_patterns():
    """Run brain pattern detection in-process."""
    try:
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from brain_db import detect_patterns
        patterns = detect_patterns(days=7)
        logger.info(f"Brain pattern detection found {len(patterns)} patterns")
    except Exception as e:
        logger.error(f"Brain pattern detection failed: {e}")


def _run_job(name: str):
    """Execute a scheduled job by name."""
    if name not in JOB_COMMANDS:
        logger.warning(f"Unknown job: {name}")
        return

    # Handle in-process jobs
    if name == "brain_pattern_detection":
        _run_brain_patterns()
        return

    cmd = JOB_COMMANDS[name]
    logger.info(f"Running scheduled job: {name}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info(f"Job {name} completed successfully")
        else:
            logger.error(f"Job {name} failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error(f"Job {name} timed out after 300s")
    except Exception as e:
        logger.error(f"Job {name} error: {e}")


def _cron_to_schedule_time(cron_schedule: str) -> str | None:
    """
    Convert simple cron schedule to schedule library format.
    Only supports: "M H * * *" format (daily at H:M).

    Returns time string like "07:00" or None if unsupported.
    """
    parts = cron_schedule.strip().split()
    if len(parts) != 5:
        return None

    minute, hour, day, month, dow = parts

    # Only support daily schedules (day=*, month=*, dow=*)
    if day != "*" or month != "*" or dow != "*":
        logger.warning(f"Unsupported cron schedule (only daily supported): {cron_schedule}")
        return None

    try:
        h = int(hour)
        m = int(minute)
        return f"{h:02d}:{m:02d}"
    except ValueError:
        logger.warning(f"Invalid cron schedule: {cron_schedule}")
        return None


def _parse_dow_field(dow_str: str) -> list[str]:
    """Parse a cron DOW field into a list of day names.

    Supports single values ('0'), comma-separated ('1,3,5'), and ranges ('1-5').
    Returns deduplicated day names, or empty list on parse error.
    """
    if dow_str == "*":
        return []

    day_nums: set[int] = set()
    for part in dow_str.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                for i in range(int(start), int(end) + 1):
                    day_nums.add(i)
            except (ValueError, TypeError):
                return []
        else:
            try:
                day_nums.add(int(part))
            except (ValueError, TypeError):
                return []

    names = []
    seen: set[str] = set()
    for num in sorted(day_nums):
        name = DOW_MAP.get(str(num))
        if not name:
            logger.warning(f"Invalid DOW value: {num}")
            return []
        if name not in seen:
            names.append(name)
            seen.add(name)
    return names


def _schedule_from_cron(name: str, cron_schedule: str) -> bool:
    """Schedule daily, hourly-interval, or day-of-week jobs."""
    parts = cron_schedule.strip().split()
    if len(parts) != 5:
        return False

    minute, hour, day, month, dow = parts
    if month != "*":
        logger.warning(f"Unsupported cron schedule (monthly not supported): {cron_schedule}")
        return False

    # Day-of-week schedule: "M H * * DOW"
    if dow != "*" and day == "*":
        day_names = _parse_dow_field(dow)
        if not day_names:
            logger.warning(f"Failed to parse DOW field: {dow}")
            return False
        try:
            h = int(hour)
            m = int(minute)
            time_str = f"{h:02d}:{m:02d}"
        except ValueError:
            logger.warning(f"Invalid time in DOW schedule: {cron_schedule}")
            return False
        for day_name in day_names:
            getattr(schedule.every(), day_name).at(time_str).do(_run_job, name)
        logger.info(f"Scheduled {name} on {', '.join(day_names)} at {time_str}")
        return True

    if day != "*" or dow != "*":
        logger.warning(f"Unsupported cron schedule: {cron_schedule}")
        return False

    time_str = _cron_to_schedule_time(cron_schedule)
    if time_str:
        schedule.every().day.at(time_str).do(_run_job, name)
        logger.info(f"Scheduled {name} at {time_str}")
        return True

    if minute.isdigit() and hour.startswith("*/") and hour[2:].isdigit():
        interval = int(hour[2:])
        if interval <= 0:
            return False
        schedule.every(interval).hours.at(f":{int(minute):02d}").do(_run_job, name)
        logger.info(f"Scheduled {name} every {interval} hours at minute {minute}")
        return True

    logger.warning(f"Unsupported cron schedule: {cron_schedule}")
    return False


def load_and_schedule_jobs():
    """Load jobs from config and schedule them."""
    schedule.clear()  # Clear any existing jobs

    if not CRON_CONFIG.exists():
        logger.info("No cron config found, no jobs scheduled")
        return 0

    try:
        config = json.loads(CRON_CONFIG.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load cron config: {e}")
        return 0

    scheduled = 0
    for name, entry in config.items():
        if name not in JOB_COMMANDS:
            logger.warning(f"Unknown job in config: {name}")
            continue

        if not entry.get("enabled", False):
            continue

        cron_schedule = entry.get("schedule", "")
        if not _schedule_from_cron(name, cron_schedule):
            continue
        scheduled += 1

    return scheduled


def _scheduler_loop():
    """Main scheduler loop - runs in background thread."""
    global _last_v2_housekeeping
    logger.info("Scheduler thread started")
    while True:
        try:
            schedule.run_pending()
            now = time.time()
            if now - _last_v2_housekeeping >= 300:
                _run_v2_housekeeping()
                _last_v2_housekeeping = now
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        time.sleep(30)  # Check every 30 seconds


_scheduler_thread: threading.Thread | None = None


def start_scheduler():
    """Start the background scheduler thread."""
    global _scheduler_thread

    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        logger.warning("Scheduler already running")
        return

    count = load_and_schedule_jobs()
    logger.info(f"Loaded {count} scheduled jobs")

    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="scheduler")
    _scheduler_thread.start()
    logger.info("Background scheduler started")


def reload_jobs():
    """Reload jobs from config without restarting scheduler."""
    count = load_and_schedule_jobs()
    logger.info(f"Reloaded {count} scheduled jobs")
    return count


def get_next_runs() -> dict[str, str]:
    """Get next run times for all scheduled jobs."""
    jobs = {}
    for job in schedule.get_jobs():
        # Extract job name from the job's function args
        if job.job_func.args:
            name = job.job_func.args[0]
            next_run = job.next_run
            if next_run:
                jobs[name] = next_run.strftime("%Y-%m-%d %H:%M:%S")
    return jobs
