from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

from v2.domain.models import ResolvedNow
from v2.interfaces.ports import Clock
from v2.infra.sqlite_state_store import DEFAULT_TIMEZONE, SQLiteStateStore

UTC_OFFSET_RE = re.compile(r"^(?:UTC)?(?P<sign>[+-])(?P<hour>\d{1,2})(?::?(?P<minute>\d{2}))?$", re.IGNORECASE)


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ParsedTimezone:
    tzinfo: tzinfo
    canonical_name: str
    label: str


def parse_timezone_spec(spec: str) -> ParsedTimezone:
    raw = (spec or "").strip()
    if not raw:
        raw = DEFAULT_TIMEZONE

    try:
        zone = ZoneInfo(raw)
        return ParsedTimezone(zone, raw, raw)
    except Exception:
        pass

    normalized = raw.upper().replace("UTC", "")
    if normalized in {"Z", "+0", "+00", "+00:00", "-0", "-00", "-00:00"}:
        return ParsedTimezone(timezone.utc, "UTC+00:00", "UTC+00:00")

    match = UTC_OFFSET_RE.match(raw)
    if not match:
        match = UTC_OFFSET_RE.match(normalized)
    if not match:
        zone = ZoneInfo(DEFAULT_TIMEZONE)
        return ParsedTimezone(zone, DEFAULT_TIMEZONE, DEFAULT_TIMEZONE)

    sign = 1 if match.group("sign") == "+" else -1
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or "00")
    offset = timedelta(hours=hour, minutes=minute) * sign
    label = f"UTC{match.group('sign')}{hour:02d}:{minute:02d}"
    return ParsedTimezone(timezone(offset, name=label), label, label)


class DefaultTimezoneResolver:
    def __init__(self, store: SQLiteStateStore, clock: Clock | None = None):
        self.store = store
        self.clock = clock or SystemClock()

    def resolve_now(self, chat_id: int) -> ResolvedNow:
        tz_name = self.store.resolve_timezone_name(chat_id)
        parsed = parse_timezone_spec(tz_name)
        utc_now = self.clock.now_utc()
        local_now = utc_now.astimezone(parsed.tzinfo)
        local_date = local_now.date().isoformat()
        return ResolvedNow(
            chat_id=chat_id,
            timezone_name=parsed.canonical_name,
            timezone_label=parsed.label,
            utc_now=utc_now,
            local_now=local_now,
            local_date=local_date,
            day_key=local_date,
        )

    def set_current_timezone(
        self,
        chat_id: int,
        timezone: str,
        source: str,
        location_label: str | None = None,
    ) -> ResolvedNow:
        parsed = parse_timezone_spec(timezone)
        self.store.set_current_timezone(
            chat_id=chat_id,
            timezone_name=parsed.canonical_name,
            source=source,
            location_label=location_label or "",
        )
        return self.resolve_now(chat_id)
