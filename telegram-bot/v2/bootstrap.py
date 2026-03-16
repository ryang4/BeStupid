from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from v2.app.context_assembler import ContextAssemblerImpl
from v2.app.memory_review import MemoryReviewServiceImpl
from v2.app.projection import PrivateProjectionService
from v2.app.reminder_policy import SimpleReminderPolicy
from v2.app.timezone_resolver import DefaultTimezoneResolver, SystemClock
from v2.infra.sqlite_state_store import SQLiteStateStore


@dataclass(frozen=True)
class Services:
    store: SQLiteStateStore
    clock: SystemClock
    timezone_resolver: DefaultTimezoneResolver
    context_assembler: ContextAssemblerImpl
    memory_review: MemoryReviewServiceImpl
    projection: PrivateProjectionService
    reminder_policy: SimpleReminderPolicy


@lru_cache(maxsize=1)
def get_services() -> Services:
    store = SQLiteStateStore()
    store.init_schema()
    clock = SystemClock()
    resolver = DefaultTimezoneResolver(store=store, clock=clock)
    return Services(
        store=store,
        clock=clock,
        timezone_resolver=resolver,
        context_assembler=ContextAssemblerImpl(store=store, resolver=resolver),
        memory_review=MemoryReviewServiceImpl(store=store),
        projection=PrivateProjectionService(store=store),
        reminder_policy=SimpleReminderPolicy(store=store, resolver=resolver),
    )
