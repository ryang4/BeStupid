from __future__ import annotations

from typing import Any

from v2.domain.models import ContextBlock, PromptEnvelope
from v2.interfaces.ports import TimezoneResolver
from v2.infra.sqlite_state_store import SQLiteStateStore


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
            ContextBlock("session_summary", self._render_session_block(session), priority=2),
            ContextBlock("active_open_loops", self._render_open_loops(open_loops), priority=3),
            ContextBlock("approved_memories", self._render_memories(memories), priority=4),
            ContextBlock("recent_corrections", self._render_corrections(corrections), priority=5),
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
        return "\n".join(lines)

    def _render_session_block(self, session: dict[str, Any]) -> str:
        if not session or not session.get("summary_text"):
            return ""
        lines = ["SESSION SUMMARY:", f"- Summary: {session['summary_text'][:220]}"]
        topics = session.get("active_topics_json")
        if topics:
            try:
                parsed_topics = __import__("json").loads(topics)
            except Exception:
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
