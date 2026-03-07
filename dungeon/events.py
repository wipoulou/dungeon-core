"""EventBus: central event system. No system talks to another directly.

All meaningful state changes fire an Event. Systems subscribe to the types they
care about. The bus maintains a queryable log — the primary debugging tool for
understanding why an entity made a decision.

Usage:
    bus = EventBus()
    bus.subscribe(EventType.BELIEF_VIOLATED, my_handler)
    bus.fire(Event(EventType.BELIEF_VIOLATED, actor_id="adv_1", ...))

    # Debug: what happened in the last run?
    for e in bus.get_log(EventType.DAMAGE_DEALT):
        print(e)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


class EventType(Enum):
    # Belief / knowledge
    BELIEF_VIOLATED     = auto()  # entity found something different from expectation
    BELIEF_UPDATED      = auto()  # entity updated a belief (no conflict)
    KNOWLEDGE_SYNCED    = auto()  # two entities synced knowledge

    # Combat / damage
    DAMAGE_DEALT        = auto()  # entity took damage (source, amount, remaining_hp)
    ENTITY_DIED         = auto()  # entity HP reached 0
    ENTITY_RESPAWNED    = auto()  # mob respawned at home position

    # Traps
    TRAP_TRIGGERED      = auto()  # adventurer triggered a trap
    PROJECTILE_HIT      = auto()  # arrow/projectile hit an entity

    # AI / state
    STATE_CHANGED       = auto()  # entity transitioned between AI states
    MOB_SPOTTED         = auto()  # entity spotted a hostile
    MOB_LOST            = auto()  # entity lost track of a hostile

    # Loot / economy
    CHEST_LOOTED        = auto()  # adventurer looted a chest
    CHEST_EMPTY         = auto()  # adventurer found expected chest empty
    ITEM_DROPPED        = auto()  # item dropped on death or deliberate
    ITEM_PICKED_UP      = auto()  # entity picked up a dropped item
    MANA_GENERATED      = auto()  # mana earned this tick (source, amount)

    # Spells (future)
    SPELL_CAST          = auto()  # entity cast a spell (type, cost, targets)
    SPELL_EFFECT        = auto()  # spell effect applied to a target

    # Party
    PARTY_SYNCED        = auto()  # party shared knowledge between members
    MEMBER_EXITED       = auto()  # party member reached exit
    MEMBER_DIED         = auto()  # party member died (affects sympathy)

    # Meta / dungeon
    RAID_STARTED        = auto()  # rumor threshold hit, raid begins
    DUNGEON_THRESHOLD   = auto()  # dungeon hit a power milestone


@dataclass
class Event:
    type: EventType
    actor_id: str                          # who caused this event
    location: tuple[int, int] = (0, 0)    # where it happened
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0                # game time


Handler = Callable[[Event], None]


class EventBus:
    """Central event bus with a queryable, filterable log.

    The log is the primary observability tool — it records every event that
    fired, with full context, in order. Can be filtered by type, actor, time
    range, or location.
    """

    def __init__(self, log_enabled: bool = True) -> None:
        self._subscribers: dict[EventType, list[Handler]] = {}
        self._log: list[Event] = []
        self.log_enabled = log_enabled

    # ------------------------------------------------------------------
    # Subscribe / fire
    # ------------------------------------------------------------------

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: EventType, handler: Handler) -> None:
        handlers = self._subscribers.get(event_type, [])
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    def fire(self, event: Event) -> None:
        if self.log_enabled:
            self._log.append(event)
        for handler in self._subscribers.get(event.type, []):
            handler(event)

    def fire_many(self, events: list[Event]) -> None:
        for e in events:
            self.fire(e)

    # ------------------------------------------------------------------
    # Log queries
    # ------------------------------------------------------------------

    def get_log(
        self,
        event_type: EventType | None = None,
        actor_id: str | None = None,
        since: float | None = None,
        location: tuple[int, int] | None = None,
    ) -> list[Event]:
        """Return filtered log entries. All filters are AND-combined."""
        result = self._log
        if event_type is not None:
            result = [e for e in result if e.type == event_type]
        if actor_id is not None:
            result = [e for e in result if e.actor_id == actor_id]
        if since is not None:
            result = [e for e in result if e.timestamp >= since]
        if location is not None:
            result = [e for e in result if e.location == location]
        return result

    def last(self, event_type: EventType | None = None) -> Event | None:
        """Return the most recent event (of given type if specified)."""
        log = self.get_log(event_type)
        return log[-1] if log else None

    def count(self, event_type: EventType | None = None, actor_id: str | None = None) -> int:
        return len(self.get_log(event_type=event_type, actor_id=actor_id))

    def clear_log(self) -> None:
        self._log.clear()

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def dump(
        self,
        event_type: EventType | None = None,
        actor_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """Human-readable log dump. Most recent events first."""
        entries = list(reversed(self.get_log(event_type, actor_id, since)))
        if limit is not None:
            entries = entries[:limit]
        return [
            {
                "t": round(e.timestamp, 3),
                "type": e.type.name,
                "actor": e.actor_id,
                "loc": e.location,
                "data": e.data,
            }
            for e in entries
        ]

    def summary(self) -> dict[str, int]:
        """Count of events by type — quick overview of what happened."""
        result: dict[str, int] = {}
        for e in self._log:
            result[e.type.name] = result.get(e.type.name, 0) + 1
        return dict(sorted(result.items(), key=lambda x: -x[1]))

    def __len__(self) -> int:
        return len(self._log)

    def __repr__(self) -> str:
        return f"EventBus({len(self._log)} events logged)"
