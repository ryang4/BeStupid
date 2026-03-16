"""
Production-safe tool registry for BeStupid V2.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from v2.bootstrap import get_services
from v2.app.timezone_resolver import parse_timezone_spec

ALLOWED_METRICS = ["Weight", "Sleep", "Sleep_Quality", "Mood_AM", "Mood_PM", "Energy", "Focus"]

TOOLS = [
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
        "name": "append_food",
        "description": "Append a food entry to canonical day state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "date": {"type": "string", "description": "Optional YYYY-MM-DD in local time."},
            },
            "required": ["description"],
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
        "name": "queue_memory_candidates",
        "description": "Run the review-before-save extractor over explicit user text and queue pending memory candidates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "review_memory_candidate",
        "description": "Approve or reject a pending memory candidate.",
        "input_schema": {
            "type": "object",
            "properties": {
                "candidate_id": {"type": "string"},
                "action": {"type": "string", "enum": ["approve", "reject"]},
            },
            "required": ["candidate_id", "action"],
        },
    },
]


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
    return f"Updated {field}={result['value']} for {local_date}."


def append_food(chat_id: int, description: str, date: str | None = None) -> str:
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    result = services.store.append_food(chat_id, local_date, description)
    snapshot = services.store.get_day_snapshot(chat_id, local_date)
    if snapshot:
        services.projection.render_private_day_log(snapshot.day_id)
    return f"Logged food for {local_date}: {result['description']}"


def mark_habit(chat_id: int, habit_id: str, status: str, date: str | None = None) -> str:
    services = get_services()
    local_date = _resolve_local_date(chat_id, date)
    result = services.store.mark_habit(chat_id, local_date, habit_id, status)
    snapshot = services.store.get_day_snapshot(chat_id, local_date)
    if snapshot:
        services.projection.render_private_day_log(snapshot.day_id)
    return f"Marked habit {result['habit_id']} as {result['status']} for {local_date}."


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
    return f"Created {kind} loop {created['loop_id']}: {created['title']}"


def complete_open_loop(chat_id: int, loop_id_or_title: str) -> str:
    services = get_services()
    result = services.store.complete_open_loop(chat_id, loop_id_or_title)
    if not result:
        return f"No open loop found for {loop_id_or_title}."
    snapshot = services.store.get_day_snapshot(chat_id)
    if snapshot:
        services.projection.render_private_day_log(snapshot.day_id)
    return f"Completed loop {result['loop_id']}: {result['title']}"


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


async def execute_tool(name: str, inputs: dict, chat_id: int = 0) -> str:
    if name == "get_day_snapshot":
        return get_day_snapshot(chat_id, inputs.get("date"))
    if name == "set_timezone":
        return set_timezone(chat_id, inputs["timezone"], inputs.get("location_label"))
    if name == "update_day_metric":
        return update_day_metric(chat_id, inputs["field"], inputs["value"], inputs.get("date"))
    if name == "append_food":
        return append_food(chat_id, inputs["description"], inputs.get("date"))
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
    if name == "queue_memory_candidates":
        return queue_memory_candidates(chat_id, inputs["text"])
    if name == "review_memory_candidate":
        return review_memory_candidate(chat_id, inputs["candidate_id"], inputs["action"])
    return f"Unknown V2 tool: {name}"
