from __future__ import annotations

import json
import os
from pathlib import Path

from v2.infra.sqlite_state_store import PRIVATE_DAY_LOG_DIR, PRIVATE_DIR, SQLiteStateStore


class PrivateProjectionService:
    def __init__(self, store: SQLiteStateStore):
        self.store = store
        PRIVATE_DAY_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def render_private_day_log(self, day_id: str) -> Path:
        data = self.store.render_private_day_log_data(day_id)
        if not data:
            raise ValueError(f"Unknown day_id: {day_id}")

        out_path = PRIVATE_DAY_LOG_DIR / f"{data['local_date']}.md"
        lines = [
            f"# Private Day Log - {data['local_date']}",
            "",
            f"- Timezone: {data['timezone']}",
            f"- Status: {data['status']}",
            f"- State version: {data['state_version']}",
            "",
            "## Metrics",
        ]
        metrics = data.get("metrics", {})
        if metrics:
            for field, value in sorted(metrics.items()):
                lines.append(f"- {field}: {value}")
        else:
            lines.append("- None")

        lines.extend(["", "## Habits"])
        habits = data.get("habits", [])
        if habits:
            for habit in habits:
                lines.append(f"- {habit['name']}: {habit['status']}")
        else:
            lines.append("- None")

        lines.extend(["", "## Food"])
        foods = data.get("foods", [])
        if foods:
            for food in foods:
                lines.append(f"- {food['logged_at_utc']}: {food['description']}")
        else:
            lines.append("- None")

        lines.extend(["", "## Open Loops"])
        loops = data.get("open_loops", [])
        if loops:
            for loop in loops:
                due = f" (due {loop['due_at_utc']})" if loop.get("due_at_utc") else ""
                lines.append(f"- [{loop['priority']}] {loop['title']}{due}")
        else:
            lines.append("- None")

        if data.get("summary"):
            lines.extend(["", "## Session Summary", data["summary"]])

        out_path.write_text("\n".join(lines) + "\n")
        self.store.export_private_metrics(data["chat_id"])
        return out_path

    def render_all_private_state(self, chat_id: int) -> Path:
        out_path = PRIVATE_DIR / "assistant_state.snapshot.json"
        snapshot = {
            "chat_id": chat_id,
            "days": {},
        }
        current = self.store.get_day_snapshot(chat_id)
        if current:
            snapshot["days"][current.local_date] = {
                "metrics": current.metrics,
                "habits": current.habits,
                "foods": current.foods,
                "open_loops": current.open_loops,
            }
        out_path.write_text(json.dumps(snapshot, indent=2))
        return out_path
