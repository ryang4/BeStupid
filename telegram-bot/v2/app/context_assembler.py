from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from v2.domain.models import ContextBlock, PromptEnvelope
from v2.interfaces.ports import TimezoneResolver
from v2.infra.sqlite_state_store import SQLiteStateStore

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", str(Path(__file__).resolve().parents[3])))
BRAIN_DB_PATH = PROJECT_ROOT / "memory" / "brain.db"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class ContextAssemblerImpl:
    def __init__(self, store: SQLiteStateStore, resolver: TimezoneResolver, max_dynamic_tokens: int = 2500):
        self.store = store
        self.resolver = resolver
        self.max_dynamic_tokens = max_dynamic_tokens

    def get_recent_messages(self, chat_id: int, max_pairs: int = 4) -> list[dict[str, str]]:
        return self.store.list_recent_messages(chat_id, max_pairs=max_pairs)

    def build(self, chat_id: int, user_text: str) -> PromptEnvelope:
        resolved = self.resolver.resolve_now(chat_id)
        self.store.ensure_day_open(resolved)
        day = self.store.get_day_snapshot(chat_id, resolved.local_date)
        session = self.store.get_latest_session_summary(chat_id) or {}
        memories = self.store.get_approved_memories(chat_id, limit=6)
        corrections = self.store.list_recent_corrections(chat_id, limit=2)
        open_loops = self.store.list_due_followups(chat_id, now_utc=resolved.utc_now, limit=5)
        recent_messages = self.get_recent_messages(chat_id, max_pairs=4)

        blocks = [
            ContextBlock("timezone_and_clock_snapshot", self._render_timezone_block(resolved), priority=0, always_include=True),
            ContextBlock("current_day_snapshot", self._render_day_block(day), priority=1, always_include=True),
            ContextBlock("analytics_dimensions", self._render_analytics_dimensions(chat_id), priority=2, always_include=True),
            ContextBlock("session_summary", self._render_session_block(session), priority=3),
            ContextBlock("active_open_loops", self._render_open_loops(open_loops), priority=4),
            ContextBlock("active_interventions", self._render_interventions(chat_id), priority=5),
            ContextBlock("approved_memories", self._render_memories(memories), priority=6),
            ContextBlock("recent_corrections", self._render_corrections(corrections), priority=7),
            ContextBlock("brain_context", self._render_brain_context(), priority=8),
        ]

        selected_texts: list[str] = []
        selected_blocks: list[str] = []
        used_tokens = 0
        for block in sorted(blocks, key=lambda item: (not item.always_include, item.priority)):
            if not block.text.strip():
                continue
            est = _estimate_tokens(block.text)
            if block.always_include or used_tokens + est <= self.max_dynamic_tokens:
                selected_texts.append(block.text)
                selected_blocks.append(block.name)
                used_tokens += est

        if used_tokens > self.max_dynamic_tokens and recent_messages:
            recent_messages = recent_messages[-4:]

        dynamic_text = "\n\n".join(selected_texts)
        return PromptEnvelope(
            dynamic_system_prompt=dynamic_text,
            recent_messages=recent_messages,
            selected_blocks=selected_blocks,
            estimated_tokens=used_tokens,
        )

    def _render_timezone_block(self, resolved) -> str:
        return (
            "TIMEZONE AND CLOCK SNAPSHOT:\n"
            f"- Local datetime: {resolved.local_now.isoformat(timespec='minutes')}\n"
            f"- Local date: {resolved.local_date}\n"
            f"- Timezone: {resolved.timezone_label}"
        )

    def _render_day_block(self, day) -> str:
        if not day:
            return "CURRENT DAY SNAPSHOT:\n- No day state is open yet."
        lines = [
            "CURRENT DAY SNAPSHOT:",
            f"- Date: {day.local_date}",
            f"- Status: {day.status}",
            f"- Timezone: {day.timezone}",
            f"- State version: {day.state_version}",
        ]
        if day.metrics:
            metric_items = ", ".join(f"{k}={v}" for k, v in sorted(day.metrics.items()))
            lines.append(f"- Metrics: {metric_items}")
        if day.habits:
            habit_items = ", ".join(f"{item['name']}={item['status']}" for item in day.habits[:5])
            lines.append(f"- Habits: {habit_items}")
        if day.foods:
            lines.append(f"- Foods logged today: {len(day.foods)}")
        if day.open_loops:
            lines.append(f"- Open loops for today: {len(day.open_loops)}")
        if day.todos:
            total = len(day.todos)
            done = sum(1 for t in day.todos if t.get("status") == "completed")
            open_todos = [t for t in day.todos if t.get("status") == "open"]
            must_wins = [t for t in open_todos if t.get("category") == "must_win"]
            zombies = [t for t in open_todos if int(t.get("rollover_count", 0)) >= 3]
            lines.append(f"- Todos: {done}/{total} done")
            if must_wins:
                mw_names = ", ".join(t["title"][:40] for t in must_wins[:3])
                lines.append(f"- Must-win pending: {mw_names}")
            if zombies:
                z_names = ", ".join(f"{t['title'][:30]} (rolled {t['rollover_count']}x)" for t in zombies[:3])
                lines.append(f"- ZOMBIE TASKS (3+ rollovers): {z_names}")
        if day.reflections and any(day.reflections.get(k) for k in ("went_well", "went_poorly", "lessons")):
            lines.append("- Reflections: recorded")
        return "\n".join(lines)

    def _render_session_block(self, session: dict[str, Any]) -> str:
        if not session or not session.get("summary_text"):
            return ""
        lines = ["SESSION SUMMARY:", f"- Summary: {session['summary_text'][:220]}"]
        topics = session.get("active_topics_json")
        if topics:
            try:
                parsed_topics = json.loads(topics)
            except (json.JSONDecodeError, TypeError):
                parsed_topics = []
            if parsed_topics:
                lines.append(f"- Active topics: {', '.join(parsed_topics[:4])}")
        return "\n".join(lines)

    def _render_open_loops(self, open_loops: list[dict[str, Any]]) -> str:
        if not open_loops:
            return ""
        lines = ["ACTIVE OPEN LOOPS:"]
        for item in open_loops[:5]:
            suffix = f" due {item['due_at_utc']}" if item.get("due_at_utc") else ""
            lines.append(f"- [{item['priority']}] {item['title']}{suffix}")
        return "\n".join(lines)

    def _render_memories(self, memories: list[dict[str, Any]]) -> str:
        if not memories:
            return ""
        lines = ["APPROVED MEMORIES:"]
        for memory in memories[:6]:
            payload = memory.get("payload", {})
            lines.append(f"- [{memory['kind']}] {payload}")
        return "\n".join(lines)

    def _render_corrections(self, corrections: list[dict[str, Any]]) -> str:
        if not corrections:
            return ""
        lines = ["RECENT CORRECTIONS:"]
        for item in corrections[:2]:
            lines.append(f"- {item['summary']}")
        return "\n".join(lines)

    def _render_analytics_dimensions(self, chat_id: int) -> str:
        """Render available analytics dimensions so the LLM knows what data exists."""
        try:
            with self.store._connect() as conn:
                min_date_row = conn.execute(
                    "SELECT MIN(local_date) AS min_d FROM day_context WHERE chat_id = ?", (chat_id,)
                ).fetchone()
                min_date = min_date_row["min_d"] if min_date_row else "unknown"

                habit_rows = conn.execute(
                    "SELECT name FROM habit_definition WHERE chat_id = ? AND active = 1 ORDER BY name",
                    (chat_id,),
                ).fetchall()
                habit_names = [r["name"] for r in habit_rows]
        except Exception:
            min_date = "unknown"
            habit_names = []

        lines = [
            "ANALYTICS DIMENSIONS:",
            "- Metrics: Weight, Sleep, Sleep_Quality, Mood_AM, Mood_PM, Energy, Focus",
            f"- Habits: {', '.join(habit_names) if habit_names else '(none defined)'}",
            f"- Data range: {min_date} to present",
            "- Databases: assistant_state (day tracking), brain (documents, entities)",
            "- Query tools: metric_trend, habit_completion, nutrition_summary, correlate, get_computed_insights, run_query",
        ]
        return "\n".join(lines)

    def _render_interventions(self, chat_id: int) -> str:
        """Render active interventions for the system prompt."""
        try:
            interventions = self.store.list_interventions(chat_id, status="active", limit=5)
            if not interventions:
                return ""
            lines = ["ACTIVE INTERVENTIONS:"]
            for intv in interventions:
                baseline = f"{intv['baseline_value']:.1f}" if intv.get("baseline_value") is not None else "?"
                lines.append(
                    f"- \"{intv['strategy_text']}\" targeting {intv['target_metric']} "
                    f"(baseline: {baseline}, eval: {intv['evaluation_date']})"
                )
            return "\n".join(lines)
        except Exception:
            return ""

    def _render_brain_context(self) -> str:
        """Render relevant brain_db context (patterns, preferences). Gracefully degrades."""
        if not BRAIN_DB_PATH.exists():
            return ""
        try:
            import sys
            scripts_dir = str(PROJECT_ROOT / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            import brain_db

            parts = ["BRAIN CONTEXT:"]
            patterns = brain_db.get_active_patterns(min_confidence=0.5)
            for p in patterns[:3]:
                parts.append(f"- Pattern: {str(p.get('description', ''))[:100]}")
            prefs = brain_db.get_preferences()
            for p in prefs[:5]:
                parts.append(f"- Pref: {p.get('key', '')}: {str(p.get('value', ''))[:80]}")
            return "\n".join(parts) if len(parts) > 1 else ""
        except Exception:
            logger.debug("Brain context unavailable", exc_info=True)
            return ""
