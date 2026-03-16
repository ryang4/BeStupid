from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from v2.domain.models import DaySnapshot, MemoryCandidateRecord, PromptEnvelope, ReminderAction, ResolvedNow


class Clock(Protocol):
    def now_utc(self) -> datetime:
        ...


class TimezoneResolver(Protocol):
    def resolve_now(self, chat_id: int) -> ResolvedNow:
        ...

    def set_current_timezone(
        self,
        chat_id: int,
        timezone: str,
        source: str,
        location_label: str | None = None,
    ) -> ResolvedNow:
        ...


class StateStore(Protocol):
    def init_schema(self) -> None:
        ...

    def mark_update_processed(self, chat_id: int, update_id: int) -> bool:
        ...

    def ensure_day_open(self, resolved_now: ResolvedNow) -> dict:
        ...

    def get_day_snapshot(self, chat_id: int, local_date: str | None = None) -> DaySnapshot | None:
        ...

    def list_recent_messages(self, chat_id: int, max_pairs: int = 4) -> list[dict[str, str]]:
        ...


class ContextAssembler(Protocol):
    def build(self, chat_id: int, user_text: str) -> PromptEnvelope:
        ...


class ReminderPolicy(Protocol):
    def next_actions(self, chat_id: int, now_utc: datetime) -> list[ReminderAction]:
        ...


class ProjectionService(Protocol):
    def render_private_day_log(self, day_id: str) -> Path:
        ...


class MemoryReviewService(Protocol):
    def extract_candidates(self, chat_id: int, turn_id: str, text: str) -> list[MemoryCandidateRecord]:
        ...


class ModelClient(Protocol):
    async def complete(self, chat_id: int, prompt: PromptEnvelope, user_text: str) -> str:
        ...
