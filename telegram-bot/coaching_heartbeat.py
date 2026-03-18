"""
Adaptive coaching heartbeat for BeStupid Telegram bot.

Replaces the system-metrics heartbeat with Claude-generated coaching
check-ins based on Ryan's actual day. Uses claude -p (one-shot, no tools)
via Max subscription at $0/token.
"""

import asyncio
import json
import logging
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable

import requests

logger = logging.getLogger(__name__)

COACHING_MODEL = "haiku"

# Time windows: (start_hour, end_hour, name)
WINDOWS = [
    (7, 8, "morning"),
    (11, 13, "midday"),
    (15, 16, "afternoon"),
    (20, 21, "evening"),
]

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", 0))
PRIVATE_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))
HEARTBEAT_FILE = PRIVATE_DIR / "heartbeat.txt"


def evaluate_checkin(
    now: datetime,
    last_checkin_time: datetime | None,
    last_activity: datetime | None,
    mute_until: datetime | None,
    windows_sent: set[str],
) -> str | None:
    """Return window name if check-in warranted, None otherwise.

    Pure function. No I/O. Testable with zero mocking.
    """
    hour = now.hour

    # Quiet hours
    if hour < 7 or hour >= 21:
        return None

    # Muted
    if mute_until and now < mute_until:
        return None

    # Rate limit: 1 per hour
    if last_checkin_time and (now - last_checkin_time).total_seconds() < 3600:
        return None

    # Find current window
    for start, end, name in WINDOWS:
        if start <= hour < end and name not in windows_sent:
            # Skip midday/afternoon if user was active recently
            if name in ("midday", "afternoon"):
                if last_activity and (now - last_activity).total_seconds() < 2700:
                    return None
            return name

    return None


class CoachingHeartbeat:
    """Adaptive coaching check-in system.

    Runs as an asyncio background task. Evaluates every 5 minutes whether
    to send a coaching check-in. Calls claude -p one-shot for message
    generation. Falls back to SimpleReminderPolicy output on CLI failure.
    """

    def __init__(
        self,
        chat_id: int,
        get_conversation: Callable,
        chat_lock: asyncio.Lock,
        services: object,
        send_telegram: Callable[[str], Awaitable[bool]],
        prompt_path: Path,
    ):
        self.chat_id = chat_id
        self.get_conversation = get_conversation
        self.chat_lock = chat_lock
        self.services = services
        self.send_telegram = send_telegram
        self.prompt_path = prompt_path

        if not prompt_path.exists():
            raise FileNotFoundError(f"Coaching prompt not found: {prompt_path}")

        self.mute_until: datetime | None = None
        self._last_checkin_time: datetime | None = None
        self._last_activity: datetime | None = None
        self._windows_sent: set[str] = set()
        self._checkin_date: str = ""
        self._running = False

    def record_activity(self):
        """Record that user activity occurred (call on each message)."""
        self._last_activity = datetime.now()

    def mute(self, duration_minutes: int) -> int:
        """Mute coaching for duration_minutes. Returns clamped value."""
        minutes = max(1, min(duration_minutes, 1440))
        self.mute_until = datetime.now() + timedelta(minutes=minutes)
        return minutes

    def unmute(self):
        """Clear mute immediately."""
        self.mute_until = None

    def is_muted(self) -> bool:
        """Check if coaching is currently muted."""
        if self.mute_until and datetime.now() < self.mute_until:
            return True
        return False

    async def run_forever(self):
        """Main loop. Evaluates every 5 min, sends ~4 check-ins/day."""
        self._running = True
        logger.info("Coaching heartbeat started")

        # Send startup notification
        await self.send_telegram("Bot online and ready.")

        while self._running:
            try:
                self._reset_daily_if_needed()
                self._update_heartbeat_file()

                decision = self._evaluate()
                if decision:
                    await self._full_checkin_cycle(decision)

            except asyncio.CancelledError:
                logger.info("Coaching heartbeat cancelled")
                break
            except Exception:
                logger.exception("Coaching heartbeat error")

            try:
                await asyncio.sleep(300)  # 5 minutes
            except asyncio.CancelledError:
                logger.info("Coaching heartbeat cancelled")
                break

    def stop(self):
        """Stop the heartbeat loop."""
        self._running = False

    def _evaluate(self) -> str | None:
        """Lightweight pre-check using in-memory state."""
        now = datetime.now()
        return evaluate_checkin(
            now=now,
            last_checkin_time=self._last_checkin_time,
            last_activity=self._last_activity,
            mute_until=self.mute_until,
            windows_sent=self._windows_sent,
        )

    async def _full_checkin_cycle(self, window: str) -> None:
        """Assemble context, call Claude, inject into history, send."""
        try:
            context = self._assemble_context(window)
            message = await self._generate_message(context)
        except Exception:
            logger.exception("Coaching CLI failed, trying fallback")
            message = self._fallback_message()
            if not message:
                logger.warning("No fallback available, skipping check-in")
                return

        # Inject into conversation history
        async with self.chat_lock:
            state = self.get_conversation(self.chat_id)
            state.history.append({"role": "assistant", "content": message})
            state.save_to_disk(self.chat_id)

        await self.send_telegram(message)

        self._last_checkin_time = datetime.now()
        self._windows_sent.add(window)
        logger.info("Coaching check-in sent: window=%s", window)

    async def _generate_message(self, context: str) -> str:
        """One-shot Claude CLI call via Max subscription ($0/token)."""
        env = {
            "HOME": os.environ.get("HOME", ""),
            "PATH": os.environ.get("PATH", ""),
        }
        token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token

        proc = await asyncio.create_subprocess_exec(
            "claude", "-p",
            "--output-format", "json",
            "--max-turns", "1",
            "--tools", "",
            "--model", COACHING_MODEL,
            "--system-prompt-file", str(self.prompt_path),
            "--no-session-persistence",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=context.encode()),
                timeout=60,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise

        if proc.returncode != 0:
            raise RuntimeError(
                f"claude -p exit {proc.returncode}: {stderr.decode()[:200]}"
            )

        outer = json.loads(stdout.decode())
        if outer.get("is_error"):
            raise RuntimeError(f"CLI error: {outer.get('subtype')}")
        return outer["result"]

    def _get_habit_streaks(self) -> dict[str, int]:
        """Query consecutive days each habit was completed (most recent streak)."""
        try:
            with self.services.store._connect() as conn:
                rows = conn.execute("""
                    SELECT hd.name, dc.local_date, hi.status
                    FROM habit_instance hi
                    JOIN habit_definition hd ON hd.habit_id = hi.habit_id
                    JOIN day_context dc ON dc.day_id = hi.day_id
                    WHERE hd.active = 1
                    ORDER BY hd.name, dc.local_date DESC
                """).fetchall()
        except (sqlite3.Error, OSError):
            return {}

        from itertools import groupby
        streaks = {}
        for name, group in groupby(rows, key=lambda r: r["name"]):
            streak = 0
            for row in group:
                if row["status"] == "done":
                    streak += 1
                else:
                    break
            streaks[name] = streak
        return streaks

    def _render_yesterday_snapshot(self) -> str:
        """Get yesterday's completion summary."""
        try:
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            snapshot = self.services.store.get_day_snapshot(self.chat_id, yesterday)
            if not snapshot:
                return ""
            parts = [f"Yesterday ({yesterday}):"]
            if snapshot.metrics:
                m = snapshot.metrics
                if m.get("Sleep"):
                    parts.append(f"  Sleep: {m['Sleep']}")
                if m.get("Weight"):
                    parts.append(f"  Weight: {m['Weight']}")
            if snapshot.habits:
                done = sum(1 for h in snapshot.habits if h["status"] == "done")
                total = len(snapshot.habits)
                parts.append(f"  Habits: {done}/{total} completed")
            return "\n".join(parts) if len(parts) > 1 else ""
        except (sqlite3.Error, OSError):
            return ""

    def _render_time_specific_prompts(self, window: str, snapshot) -> list[str]:
        """Return window-specific coaching prompts."""
        prompts = []
        metrics = snapshot.metrics if snapshot else {}
        habits = snapshot.habits if snapshot else []
        pending = [h["name"] for h in habits if h["status"] == "pending"]

        if window == "morning":
            missing = []
            if not metrics.get("Weight"):
                missing.append("Weight")
            if not metrics.get("Sleep"):
                missing.append("Sleep")
            if not metrics.get("Mood_AM"):
                missing.append("Mood_AM")
            if missing:
                prompts.append(f"Missing morning metrics: {', '.join(missing)}")

        elif window == "afternoon":
            afternoon_habits = {"Write for 1 hour", "Read for 30 min", "Post 1 Substack note"}
            still_pending = [h for h in pending if h in afternoon_habits]
            if still_pending:
                prompts.append(f"Afternoon habits pending: {', '.join(still_pending)}")

        elif window == "evening":
            if pending:
                prompts.append(f"End-of-day habits still pending: {', '.join(pending)}")
            prompts.append("Prompt: Fill out Top 3 for Tomorrow and What Went Well/Poorly")

        return prompts

    def _assemble_context(self, window: str) -> str:
        """Build the user message for Claude with today's state."""
        now = datetime.now()
        lines = [f"Current time: {now.strftime('%I:%M %p')} ({window} check-in)"]

        snapshot = None
        # Day snapshot
        try:
            snapshot = self.services.store.get_day_snapshot(
                self.chat_id, date.today().isoformat()
            )
            if snapshot:
                if snapshot.metrics:
                    metrics = ", ".join(
                        f"{k}: {v}" for k, v in sorted(snapshot.metrics.items())
                    )
                    lines.append(f"Today's metrics: {metrics}")
                else:
                    lines.append("No metrics logged yet today.")

                if snapshot.habits:
                    done = [h["name"] for h in snapshot.habits if h["status"] == "done"]
                    pending = [h["name"] for h in snapshot.habits if h["status"] == "pending"]
                    if done:
                        lines.append(f"Habits done: {', '.join(done)}")
                    if pending:
                        lines.append(f"Habits pending: {', '.join(pending)}")
                else:
                    lines.append("No habits tracked today.")

                if snapshot.foods:
                    lines.append(f"Meals logged: {len(snapshot.foods)}")
                    total_cal = 0
                    total_protein = 0
                    for food in snapshot.foods:
                        try:
                            total_cal += int(food.get("calories", 0))
                            total_protein += int(food.get("protein_g", 0))
                        except (ValueError, TypeError):
                            pass
                    if total_cal:
                        lines.append(
                            f"Total so far: {total_cal} cal, {total_protein}g protein"
                        )
                else:
                    lines.append("No meals logged yet today.")

                if snapshot.open_loops:
                    tasks = [loop["title"] for loop in snapshot.open_loops[:5]]
                    lines.append(f"Open tasks: {', '.join(tasks)}")
        except Exception:
            logger.exception("Failed to get day snapshot for coaching")
            lines.append("(Day snapshot unavailable)")

        # Habit streaks
        try:
            streaks = self._get_habit_streaks()
            if streaks:
                streak_parts = [f"{name}: {days}d" for name, days in sorted(streaks.items()) if days > 0]
                if streak_parts:
                    lines.append(f"Habit streaks: {', '.join(streak_parts)}")
        except Exception:
            pass

        # Yesterday's snapshot
        yesterday_text = self._render_yesterday_snapshot()
        if yesterday_text:
            lines.append(yesterday_text)

        # Time-specific prompts
        time_prompts = self._render_time_specific_prompts(window, snapshot)
        lines.extend(time_prompts)

        # Weekly protocol (workout schedule)
        protocol = self._read_latest_protocol()
        if protocol:
            day_name = now.strftime("%A")
            for line in protocol.split("\n"):
                if day_name in line and "|" in line:
                    lines.append(f"Today's workout ({day_name}): {line.strip()}")
                    break

        # Recent conversation (last few messages for anti-repetition)
        try:
            state = self.get_conversation(self.chat_id)
            recent = state.history[-4:]
            if recent:
                lines.append("\nRecent conversation:")
                for msg in recent:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        lines.append(f"  {role}: {content[:150]}")
        except Exception:
            pass

        return "\n".join(lines)

    def _fallback_message(self) -> str | None:
        """Format SimpleReminderPolicy output as plain text when CLI fails."""
        try:
            actions = self.services.reminder_policy.next_actions(
                self.chat_id, datetime.utcnow()
            )
            if actions:
                lines = [a.message for a in actions[:2]]
                return "\n".join(lines)
        except Exception:
            logger.exception("Fallback message generation failed")
        return None

    def _read_latest_protocol(self) -> str:
        """Read the most recent weekly protocol file."""
        try:
            project_root = Path(os.environ.get("PROJECT_ROOT", str(Path(__file__).parent.parent)))
            protocols = sorted(project_root.glob("content/config/protocol_*.md"))
            if protocols:
                return protocols[-1].read_text()[:2000]
        except Exception:
            logger.exception("Failed to read weekly protocol")
        return ""

    def _reset_daily_if_needed(self):
        """Reset windows_sent when the date changes."""
        today = date.today().isoformat()
        if self._checkin_date != today:
            self._windows_sent.clear()
            self._checkin_date = today

    def _update_heartbeat_file(self):
        """Update heartbeat.txt for Docker health check. Runs 24/7."""
        try:
            HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
            content = f"timestamp: {datetime.now().isoformat()}\nstatus: ok\n"
            tmp = HEARTBEAT_FILE.with_suffix(".tmp")
            tmp.write_text(content)
            tmp.rename(HEARTBEAT_FILE)
        except Exception:
            logger.exception("Failed to update heartbeat file")


async def _send_telegram_async(text: str) -> bool:
    """Send message via Telegram API. Async wrapper around requests."""
    if not TELEGRAM_BOT_TOKEN or not OWNER_CHAT_ID:
        logger.warning("Telegram credentials not configured")
        return False

    def _send():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": OWNER_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                # Retry without Markdown on parse failure
                payload["parse_mode"] = ""
                resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send telegram: {e}")
            return False

    return await asyncio.to_thread(_send)
