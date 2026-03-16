---
title: "feat: Adaptive Coaching Heartbeat"
type: feat
date: 2026-03-16
version: minimal
---

# Adaptive Coaching Heartbeat

## Overview

Replace the system-metrics heartbeat with Claude-generated coaching check-ins based on Ryan's actual day — daily log, weekly protocol (workouts), habits, meals, metrics. Check-ins are conversational (part of the main history), interactive (Ryan can reply), and fire at 4 natural time windows. Uses `claude -p` via Max subscription at $0/token.

## Problem Statement

The current heartbeat sends uptime/memory/job counts hourly — Ryan ignores it. The `SimpleReminderPolicy` sends rule-based nudges that feel robotic. A Claude-powered coaching heartbeat that reads the room would actually be worth reading.

## The Build

**New files:**
- `telegram-bot/coaching_heartbeat.py` (~200 LOC)
- `telegram-bot/prompts/coaching_prompt.md`
- `telegram-bot/tests/test_coaching_heartbeat.py`

**Modified files:**
- `telegram-bot/bot.py` — wire up coaching heartbeat, add `/mute` + `/unmute`
- `telegram-bot/heartbeat.py` — strip messaging, keep health metrics + health file
- `telegram-bot/scheduler.py` — remove reminder delivery from housekeeping

One PR. No schema migrations. No shared sender extraction. No V2 tools.

---

## Phase A: Coaching Engine + Tests

### `prompts/coaching_prompt.md`

Static coaching persona file. Pass directly via `--system-prompt-file` (no temp file needed).

Contents:
- Tone: honest, human, adaptive — not cheerleader, not drill sergeant
- Time-of-day framing (morning = forward-looking, evening = reflective)
- Anti-repetition (reference recent conversation, vary observations)
- Data reference (cite specific numbers from the log, not vague encouragement)
- One topic per check-in (don't pile on)

### `coaching_heartbeat.py`

```python
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

COACHING_MODEL = "haiku"

# Time windows: (start_hour, end_hour, name)
WINDOWS = [
    (7, 8, "morning"),
    (11, 13, "midday"),
    (15, 16, "afternoon"),
    (20, 21, "evening"),
]


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
            # Skip midday/afternoon if user was active recently (not morning/evening)
            if name in ("midday", "afternoon"):
                if last_activity and (now - last_activity).total_seconds() < 2700:  # 45 min
                    return None
            return name

    return None


class CoachingHeartbeat:
    def __init__(
        self,
        chat_id: int,
        get_conversation: Callable[[int], "ConversationState"],
        chat_lock: asyncio.Lock,
        services: "Services",
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
        self._cached_tz: str = ""
        self._running = False

    def record_activity(self):
        self._last_activity = datetime.now()

    def mute(self, duration_minutes: int):
        minutes = max(1, min(duration_minutes, 1440))
        self.mute_until = datetime.now() + timedelta(minutes=minutes)

    def unmute(self):
        self.mute_until = None

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
                logger.info("Coaching heartbeat stopped")
                break
            except Exception:
                logger.exception("Coaching heartbeat error")

            try:
                await asyncio.sleep(300)  # 5 minutes
            except asyncio.CancelledError:
                logger.info("Coaching heartbeat stopped")
                break

    def stop(self):
        self._running = False

    def _evaluate(self) -> str | None:
        """Lightweight pre-check. Caches timezone to avoid SQLite on every tick."""
        if not self._cached_tz:
            resolved = self.services.timezone_resolver.resolve_now(self.chat_id)
            self._cached_tz = resolved.timezone_label
        now = datetime.now()  # Use local time (container TZ matches user TZ)
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
            # CLI failed — fall back to SimpleReminderPolicy
            message = self._fallback_message()
            if not message:
                logger.warning("Coaching CLI failed and no fallback available")
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
        env = {"HOME": os.environ.get("HOME", ""), "PATH": os.environ.get("PATH", "")}
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
            raise RuntimeError(f"claude -p exit {proc.returncode}: {stderr.decode()[:200]}")

        outer = json.loads(stdout.decode())
        if outer.get("is_error"):
            raise RuntimeError(f"CLI error: {outer.get('subtype')}")
        return outer["result"]

    def _assemble_context(self, window: str) -> str:
        """Build the user message for Claude with today's state."""
        snapshot = self.services.store.get_day_snapshot(self.chat_id, date.today().isoformat())
        protocol = self._read_latest_protocol()
        history = self.get_conversation(self.chat_id).history[-6:]  # Last ~3 exchanges
        # Format into a concise context string for Claude
        # ... (implementation assembles snapshot + protocol + history + time of day)
        return context_str

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
            pass
        return None

    def _read_latest_protocol(self) -> str:
        protocols = sorted(Path("content/config").glob("protocol_*.md"))
        return protocols[-1].read_text()[:2000] if protocols else ""

    def _reset_daily_if_needed(self):
        today = date.today().isoformat()
        if self._checkin_date != today:
            self._windows_sent.clear()
            self._checkin_date = today

    def _update_heartbeat_file(self):
        """Update heartbeat.txt for Docker health check. Runs 24/7."""
        try:
            from heartbeat import HEARTBEAT_FILE
            content = f"timestamp: {datetime.now().isoformat()}\nstatus: ok\n"
            tmp = HEARTBEAT_FILE.with_suffix(".tmp")
            tmp.write_text(content)
            tmp.rename(HEARTBEAT_FILE)
        except Exception:
            logger.exception("Failed to update heartbeat file")
```

### `tests/test_coaching_heartbeat.py`

**Pure function tests (no mocking):**
- Morning window (7:30am) → `"morning"`
- Outside window (6am, 10pm) → `None`
- Muted → `None`
- Rate limited (last check-in 30 min ago) → `None`
- User active 20 min ago, midday window → `None` (suppressed)
- User active 20 min ago, morning window → `"morning"` (not suppressed)
- Evening window (8:45pm) → `"evening"`
- Window already sent → `None`
- Date rollover resets windows
- Boundary: exactly 7:00:00 → `"morning"`

**Integration tests (mocked CLI + Telegram):**
- Full cycle: context assembled, CLI called, history updated, Telegram sent
- CLI timeout → falls back to SimpleReminderPolicy output
- CLI error (is_error: true) → falls back gracefully
- CLI binary missing (FileNotFoundError) → falls back gracefully

**Lifecycle:**
- Starts, evaluates, stops cleanly on cancel
- Heartbeat file updated even when no coaching fires

**Mute:**
- `mute(60)` suppresses check-ins for 60 minutes
- `unmute()` clears immediately
- Bounds: `mute(0)` → 1 min, `mute(9999)` → 1440 min

---

## Phase B: Bot Integration

### `bot.py` changes

- `_post_init`: Create `CoachingHeartbeat` with injected deps, start as asyncio task
- `_post_shutdown`: Cancel + await coaching task
- Keep `HeartbeatMonitor` for `/health` (uptime, memory, pending jobs) — do NOT strip health file update since coaching heartbeat now handles it
- `record_activity()`: Call both heartbeat monitor and coaching heartbeat
- Add `/mute` handler: parse optional minutes arg, clamp 1-1440, call `coaching.mute()`
- Add `/unmute` handler: call `coaching.unmute()`
- Send startup notification via coaching heartbeat (replaces old heartbeat startup msg)

### `heartbeat.py` changes

- Remove: `_build_heartbeat_message`, `_build_startup_message`, `_send_telegram`, `send_heartbeat`, `send_startup_notification`, `run_forever`
- Keep: `get_health_status`, `get_uptime`, `get_memory_usage`, `get_time_since_activity`, `record_activity`, `get_pending_jobs_count`
- No longer runs as an asyncio task — just a passive health data provider for `/health`

### `scheduler.py` changes

- Remove `_send_v2_message` calls for reminders in `_run_v2_housekeeping()`
- Keep: `ensure_day_open`, `render_private_day_log`, V2 housekeeping structure
- `SimpleReminderPolicy` stays available (coaching heartbeat uses it as CLI fallback)

---

## Acceptance Criteria

### Functional
- [ ] Check-ins fire at 4 time windows during 7am-9pm
- [ ] Morning and evening always fire; midday/afternoon skip if user active in last 45min
- [ ] Check-ins reference specific data from daily log and weekly protocol
- [ ] Replies work as normal conversation turns with full context
- [ ] `/mute` and `/unmute` work (in-memory, 1-1440 min bounds)
- [ ] No check-ins during 9pm-7am
- [ ] Never more than 1 check-in per hour
- [ ] CLI failure falls back to SimpleReminderPolicy output

### Non-Functional
- [ ] $0/token (Claude CLI via Max subscription)
- [ ] Docker health check unaffected (heartbeat.txt updated 24/7)
- [ ] No duplicate nudges (scheduler reminder delivery disabled)
- [ ] No circular imports between coaching_heartbeat.py and bot.py

### Quality
- [ ] `evaluate_checkin()` is a pure function, 10+ test cases, zero mocking
- [ ] Integration tests mock CLI subprocess and Telegram
- [ ] Coaching prompt is in separate file, not hardcoded

---

## Key Decisions

- **Claude CLI one-shot** — `claude -p --tools "" --max-turns 1` via Max, $0/token
- **Asyncio task, not scheduler thread** — avoids ConversationState race conditions
- **Pure evaluate function** — testable without mocking, all decision logic in one place
- **`asyncio.create_subprocess_exec`** — doesn't block thread pool (unlike `to_thread(subprocess.run)`)
- **Mute in memory** — ephemeral by nature, restarts clear it, that's fine
- **CLI fallback to SimpleReminderPolicy** — never go silent on failure
- **No temp file for system prompt** — pass `--system-prompt-file` pointing directly at `coaching_prompt.md`
- **Minimal env for subprocess** — only HOME, PATH, CLAUDE_CODE_OAUTH_TOKEN
- **4 fixed windows, no gap triggers** — Claude sees the data and naturally addresses gaps
- **Dependency injection** — constructor takes lock, conversation getter, services, sender
