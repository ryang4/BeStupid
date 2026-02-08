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

import schedule

logger = logging.getLogger(__name__)

# Use same HISTORY_DIR as tools.py and claude_client.py
PRIVATE_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))
CRON_CONFIG = PRIVATE_DIR / "cron_jobs.json"
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).parent.parent))

# Map job names to their actual implementations
JOB_COMMANDS = {
    "morning_briefing": ["python", "scripts/send_routine_reminder.py", "morning"],
    "evening_reminder": ["python", "scripts/send_routine_reminder.py", "evening_start"],
    "evening_screens": ["python", "scripts/send_routine_reminder.py", "evening_screens"],  
    "evening_bed": ["python", "scripts/send_routine_reminder.py", "evening_bed"],
    "daily_planner": ["python", "scripts/daily_planner.py"],
    "auto_backup": ["python", "scripts/robust_git_backup.py"],
}


def _run_job(name: str):
    """Execute a scheduled job by name."""
    if name not in JOB_COMMANDS:
        logger.warning(f"Unknown job: {name}")
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
        time_str = _cron_to_schedule_time(cron_schedule)
        if not time_str:
            continue

        schedule.every().day.at(time_str).do(_run_job, name)
        logger.info(f"Scheduled {name} at {time_str}")
        scheduled += 1

    return scheduled


def _scheduler_loop():
    """Main scheduler loop - runs in background thread."""
    logger.info("Scheduler thread started")
    while True:
        try:
            schedule.run_pending()
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
