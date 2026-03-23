"""Inline keyboard builders and callback data encoding for Telegram bot.

Compact callback_data format (all < 64 bytes):
    h:{habit_id}:{action}       mark_habit()
    m:{field}:{value}           set_day_metric()
    r:{field}:{value}           set_day_metric() (rating scale)
    g:{loop_id}:{action}        goal autopsy
    s:{intervention_id}:{act}   strategy evaluation
    t:{block_key}:ack           time-block acknowledgment
"""

from __future__ import annotations

from typing import Any


def parse_callback_data(data: str) -> tuple[str, dict[str, str]]:
    """Parse compact callback data into (prefix, params).

    Returns:
        ("h", {"habit_id": "yoga", "action": "done"})
        ("m", {"field": "Weight", "value": "219"})
        ("r", {"field": "Mood_AM", "value": "4"})
        ("g", {"loop_id": "loop_abc123", "action": "drop"})
        ("s", {"intervention_id": "intv_abc12", "action": "keep"})
        ("t", {"block_key": "writing_0323", "action": "ack"})
    """
    parts = data.split(":")
    if len(parts) < 3:
        raise ValueError(f"Invalid callback data: {data}")
    prefix = parts[0]
    if prefix == "h":
        return prefix, {"habit_id": parts[1], "action": parts[2]}
    elif prefix in ("m", "r"):
        return prefix, {"field": parts[1], "value": parts[2]}
    elif prefix == "g":
        return prefix, {"loop_id": parts[1], "action": parts[2]}
    elif prefix == "s":
        return prefix, {"intervention_id": parts[1], "action": parts[2]}
    elif prefix == "t":
        return prefix, {"block_key": parts[1], "action": parts[2]}
    raise ValueError(f"Unknown callback prefix: {prefix}")


def build_morning_keyboard(
    snapshot: Any, last_weight: str | None,
) -> dict | None:
    """Morning check-in: weight ±1, mood 1-5, sleep quality 1-5, pending habits."""
    rows: list[list[dict]] = []

    # Row 1: Weight buttons (±1 from last known)
    if last_weight and not snapshot.metrics.get("Weight"):
        try:
            w = float(last_weight)
            rows.append([
                {"text": f"⚖️ {w - 1:.0f}", "callback_data": f"m:Weight:{w - 1:.0f}"},
                {"text": f"⚖️ {w:.0f}", "callback_data": f"m:Weight:{w:.0f}"},
                {"text": f"⚖️ {w + 1:.0f}", "callback_data": f"m:Weight:{w + 1:.0f}"},
            ])
        except ValueError:
            pass

    # Row 2: Mood AM (only if not already logged)
    if not snapshot.metrics.get("Mood_AM"):
        rows.append([
            {"text": f"{i}", "callback_data": f"r:Mood_AM:{i}"} for i in range(1, 6)
        ])

    # Row 3: Sleep Quality (only if not already logged)
    if not snapshot.metrics.get("Sleep_Quality"):
        rows.append([
            {"text": f"💤{i}", "callback_data": f"r:Sleep_Quality:{i}"} for i in range(1, 6)
        ])

    # Rows 4+: Pending habits, 2 per row
    _append_habit_rows(rows, snapshot.habits)

    return {"inline_keyboard": rows} if rows else None


def build_habit_keyboard(snapshot: Any) -> dict | None:
    """Midday/afternoon: pending habits only, 2 per row."""
    rows: list[list[dict]] = []
    _append_habit_rows(rows, snapshot.habits)
    return {"inline_keyboard": rows} if rows else None


def build_evening_keyboard(
    snapshot: Any,
    stale_loops: list[dict] | None = None,
) -> dict | None:
    """Evening: PM metrics + pending habits + zombie task actions."""
    rows: list[list[dict]] = []

    # Mood PM
    if not snapshot.metrics.get("Mood_PM"):
        rows.append([
            {"text": f"{i}", "callback_data": f"r:Mood_PM:{i}"} for i in range(1, 6)
        ])
    # Energy
    if not snapshot.metrics.get("Energy"):
        rows.append([
            {"text": f"⚡{i}", "callback_data": f"r:Energy:{i}"} for i in range(1, 6)
        ])
    # Focus
    if not snapshot.metrics.get("Focus"):
        rows.append([
            {"text": f"🎯{i}", "callback_data": f"r:Focus:{i}"} for i in range(1, 6)
        ])

    # Pending habits
    _append_habit_rows(rows, snapshot.habits)

    # Zombie task actions (Phase 4 — gracefully skipped if empty)
    if stale_loops:
        for loop in stale_loops[:3]:
            lid = loop["loop_id"]
            short_title = loop["title"][:20]
            rows.append([
                {"text": f"🔨 {short_title}", "callback_data": f"g:{lid}:break"},
                {"text": f"📅 {short_title}", "callback_data": f"g:{lid}:box"},
                {"text": f"🗑 {short_title}", "callback_data": f"g:{lid}:drop"},
            ])

    return {"inline_keyboard": rows} if rows else None


def build_strategy_eval_keyboard(intervention_id: str) -> dict:
    """Strategy evaluation: Keep / Adjust / Drop."""
    return {"inline_keyboard": [[
        {"text": "✅ Keep", "callback_data": f"s:{intervention_id}:keep"},
        {"text": "🔧 Adjust", "callback_data": f"s:{intervention_id}:adjust"},
        {"text": "🗑 Drop", "callback_data": f"s:{intervention_id}:drop"},
    ]]}


def build_timeblock_ack_keyboard(block_key: str) -> dict:
    """Time-block transition acknowledgment."""
    return {"inline_keyboard": [[
        {"text": "👍 Got it", "callback_data": f"t:{block_key}:ack"},
    ]]}


def _append_habit_rows(rows: list[list[dict]], habits: list[dict]) -> None:
    """Append pending habit buttons, 2 per row."""
    pending = [h for h in habits if h.get("status") == "pending"]
    for i in range(0, len(pending), 2):
        row = []
        for h in pending[i:i + 2]:
            hid = h.get("habit_id", h.get("name", "unknown"))
            name = h.get("name", hid)
            row.append({"text": f"✅ {name}", "callback_data": f"h:{hid}:done"})
        rows.append(row)
