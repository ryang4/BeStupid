from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ResolvedNow:
    chat_id: int
    timezone_name: str
    timezone_label: str
    utc_now: datetime
    local_now: datetime
    local_date: str
    day_key: str


@dataclass(frozen=True)
class ContextBlock:
    name: str
    text: str
    priority: int
    always_include: bool = False


@dataclass(frozen=True)
class PromptEnvelope:
    dynamic_system_prompt: str
    recent_messages: list[dict[str, str]]
    selected_blocks: list[str]
    estimated_tokens: int


@dataclass(frozen=True)
class MemoryCandidateRecord:
    candidate_id: str
    chat_id: int
    kind: str
    payload: dict[str, Any]
    confidence: float
    reason: str
    status: str
    created_at_utc: str


@dataclass(frozen=True)
class ReminderAction:
    chat_id: int
    reminder_kind: str
    target_id: str
    scheduled_slot_local: str
    message: str
    urgency: str = "normal"


@dataclass
class DaySnapshot:
    day_id: str
    chat_id: int
    local_date: str
    timezone: str
    status: str
    state_version: int
    metrics: dict[str, str] = field(default_factory=dict)
    foods: list[dict[str, str]] = field(default_factory=list)
    habits: list[dict[str, str]] = field(default_factory=list)
    open_loops: list[dict[str, str]] = field(default_factory=list)
    todos: list[dict[str, Any]] = field(default_factory=list)
    reflections: dict[str, str] = field(default_factory=dict)
    summary: str = ""
