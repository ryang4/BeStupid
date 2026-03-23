"""Time-block computation from protocol and habit definitions.

Pure functions. No I/O except reading passed-in data.
"""

from __future__ import annotations

from datetime import datetime


# Default habit -> time block mapping
# Format: (habit_id_substring, label, start_hour, start_min, end_hour, end_min)
HABIT_BLOCKS = [
    ("meditation", "Meditation", 7, 0, 7, 5),
    ("yoga", "Yoga", 7, 5, 7, 15),
    ("writing", "Writing", 10, 0, 11, 0),
    ("substack", "Substack", 11, 0, 11, 30),
    ("note_ideas", "Note Ideas", 11, 30, 12, 0),
    ("reading", "Reading", 14, 0, 14, 30),
]

WORKOUT_DEFAULT = ("Workout", 18, 0, 19, 0)


def compute_todays_blocks(
    protocol_text: str,
    day_name: str,
    habits: list[dict],
) -> list[dict]:
    """Compute time blocks for today from protocol + habits.

    Args:
        protocol_text: Raw protocol markdown (may be empty)
        day_name: e.g. "Monday", "Tuesday"
        habits: List of habit dicts with 'habit_id' and 'name' keys

    Returns:
        Sorted list of {label, start_hour, start_min, end_hour, end_min}
    """
    blocks: list[dict] = []

    # Habit-based blocks (only for active habits)
    active_ids = {h.get("habit_id", "").lower() for h in habits}
    for hid_sub, label, sh, sm, eh, em in HABIT_BLOCKS:
        if any(hid_sub in aid for aid in active_ids):
            blocks.append({
                "label": label,
                "start_hour": sh, "start_min": sm,
                "end_hour": eh, "end_min": em,
            })

    # Workout block from protocol
    if protocol_text and day_name:
        for line in protocol_text.split("\n"):
            if day_name in line and "|" in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2:
                    workout_label = f"Workout: {parts[1]}"
                    blocks.append({
                        "label": workout_label[:30],
                        "start_hour": WORKOUT_DEFAULT[1],
                        "start_min": WORKOUT_DEFAULT[2],
                        "end_hour": WORKOUT_DEFAULT[3],
                        "end_min": WORKOUT_DEFAULT[4],
                    })
                break

    # Sort by start time
    blocks.sort(key=lambda b: (b["start_hour"], b["start_min"]))
    return blocks


def find_upcoming_transition(
    blocks: list[dict],
    now: datetime,
    lookahead_min: int = 5,
) -> dict | None:
    """Find if current time is within lookahead_min of any block end.

    Returns {current_block, next_block, minutes_remaining} or None.
    """
    for i, block in enumerate(blocks):
        block_end = now.replace(
            hour=block["end_hour"], minute=block["end_min"], second=0, microsecond=0,
        )
        delta_seconds = (block_end - now).total_seconds()

        if 0 < delta_seconds <= lookahead_min * 60:
            next_block = blocks[i + 1] if i + 1 < len(blocks) else None
            return {
                "current_block": block,
                "next_block": next_block,
                "minutes_remaining": int(delta_seconds / 60),
            }

    return None
