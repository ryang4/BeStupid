from __future__ import annotations

from datetime import datetime, timedelta

from v2.domain.models import ReminderAction
from v2.interfaces.ports import TimezoneResolver
from v2.infra.sqlite_state_store import SQLiteStateStore


class SimpleReminderPolicy:
    def __init__(self, store: SQLiteStateStore, resolver: TimezoneResolver):
        self.store = store
        self.resolver = resolver

    def next_actions(self, chat_id: int, now_utc: datetime) -> list[ReminderAction]:
        resolved = self.resolver.resolve_now(chat_id)
        day = self.store.get_day_snapshot(chat_id, resolved.local_date)
        if not day:
            return []

        actions: list[ReminderAction] = []
        slot = resolved.local_now.strftime("%Y-%m-%dT%H:%M")
        missing_metrics = [field for field in ("Weight", "Sleep", "Energy", "Mood_AM") if field not in day.metrics]
        if day.status == "open" and missing_metrics and resolved.local_now.hour >= 8:
            actions.append(
                ReminderAction(
                    chat_id=chat_id,
                    reminder_kind="missing_morning_checkin",
                    target_id=day.day_id,
                    scheduled_slot_local=slot,
                    message=f"Missing morning check-in fields: {', '.join(missing_metrics[:3])}",
                )
            )

        for habit in day.habits:
            if habit["status"] == "pending":
                actions.append(
                    ReminderAction(
                        chat_id=chat_id,
                        reminder_kind="habit_pending",
                        target_id=habit["habit_id"],
                        scheduled_slot_local=slot,
                        message=f"Habit still pending: {habit['name']}",
                    )
                )

        for loop in self.store.list_due_followups(chat_id, now_utc=now_utc, limit=5):
            actions.append(
                ReminderAction(
                    chat_id=chat_id,
                    reminder_kind="due_followup",
                    target_id=loop["loop_id"],
                    scheduled_slot_local=slot,
                    message=f"Follow-up due: {loop['title']}",
                    urgency="high" if loop["priority"] == "high" else "normal",
                )
            )
        return actions[:6]
