"""Tests for dungeon/events.py — EventBus."""

import pytest
from dungeon.events import Event, EventBus, EventType


def make_event(
    etype: EventType = EventType.DAMAGE_DEALT,
    actor: str = "adv_1",
    loc: tuple = (5, 3),
    t: float = 1.0,
    **data,
) -> Event:
    return Event(type=etype, actor_id=actor, location=loc, data=data, timestamp=t)


class TestSubscribeAndFire:
    def test_handler_called_on_fire(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.DAMAGE_DEALT, received.append)
        e = make_event(EventType.DAMAGE_DEALT)
        bus.fire(e)
        assert received == [e]

    def test_handler_not_called_for_other_type(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.DAMAGE_DEALT, received.append)
        bus.fire(make_event(EventType.TRAP_TRIGGERED))
        assert received == []

    def test_multiple_handlers_same_type(self):
        bus = EventBus()
        calls_a, calls_b = [], []
        bus.subscribe(EventType.DAMAGE_DEALT, calls_a.append)
        bus.subscribe(EventType.DAMAGE_DEALT, calls_b.append)
        bus.fire(make_event(EventType.DAMAGE_DEALT))
        assert len(calls_a) == 1
        assert len(calls_b) == 1

    def test_unsubscribe_stops_calls(self):
        bus = EventBus()
        received = []
        handler = received.append
        bus.subscribe(EventType.DAMAGE_DEALT, handler)
        bus.unsubscribe(EventType.DAMAGE_DEALT, handler)
        bus.fire(make_event(EventType.DAMAGE_DEALT))
        assert received == []

    def test_unsubscribe_nonexistent_is_safe(self):
        bus = EventBus()
        bus.unsubscribe(EventType.DAMAGE_DEALT, lambda e: None)  # should not raise

    def test_fire_many(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.DAMAGE_DEALT, received.append)
        events = [make_event(EventType.DAMAGE_DEALT, t=float(i)) for i in range(3)]
        bus.fire_many(events)
        assert len(received) == 3


class TestLogging:
    def test_events_logged(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT))
        assert len(bus) == 1

    def test_log_disabled_skips_logging(self):
        bus = EventBus(log_enabled=False)
        bus.fire(make_event(EventType.DAMAGE_DEALT))
        assert len(bus) == 0

    def test_clear_log(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT))
        bus.clear_log()
        assert len(bus) == 0

    def test_handlers_still_called_when_log_disabled(self):
        bus = EventBus(log_enabled=False)
        received = []
        bus.subscribe(EventType.DAMAGE_DEALT, received.append)
        bus.fire(make_event(EventType.DAMAGE_DEALT))
        assert len(received) == 1


class TestGetLog:
    def test_get_all(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT))
        bus.fire(make_event(EventType.TRAP_TRIGGERED))
        assert len(bus.get_log()) == 2

    def test_filter_by_type(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT))
        bus.fire(make_event(EventType.TRAP_TRIGGERED))
        assert len(bus.get_log(EventType.DAMAGE_DEALT)) == 1
        assert bus.get_log(EventType.DAMAGE_DEALT)[0].type == EventType.DAMAGE_DEALT

    def test_filter_by_actor(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT, actor="adv_1"))
        bus.fire(make_event(EventType.DAMAGE_DEALT, actor="adv_2"))
        result = bus.get_log(actor_id="adv_1")
        assert len(result) == 1
        assert result[0].actor_id == "adv_1"

    def test_filter_by_since(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT, t=1.0))
        bus.fire(make_event(EventType.DAMAGE_DEALT, t=5.0))
        bus.fire(make_event(EventType.DAMAGE_DEALT, t=10.0))
        result = bus.get_log(since=5.0)
        assert len(result) == 2

    def test_filter_by_location(self):
        bus = EventBus()
        bus.fire(make_event(EventType.TRAP_TRIGGERED, loc=(1, 2)))
        bus.fire(make_event(EventType.TRAP_TRIGGERED, loc=(3, 4)))
        result = bus.get_log(location=(1, 2))
        assert len(result) == 1

    def test_filter_combined(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT, actor="adv_1", t=1.0))
        bus.fire(make_event(EventType.DAMAGE_DEALT, actor="adv_2", t=2.0))
        bus.fire(make_event(EventType.TRAP_TRIGGERED, actor="adv_1", t=3.0))
        result = bus.get_log(EventType.DAMAGE_DEALT, actor_id="adv_1")
        assert len(result) == 1

    def test_last_returns_most_recent(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT, t=1.0))
        bus.fire(make_event(EventType.DAMAGE_DEALT, t=2.0))
        last = bus.last(EventType.DAMAGE_DEALT)
        assert last.timestamp == pytest.approx(2.0)

    def test_last_returns_none_when_empty(self):
        bus = EventBus()
        assert bus.last() is None
        assert bus.last(EventType.DAMAGE_DEALT) is None

    def test_count(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT, actor="adv_1"))
        bus.fire(make_event(EventType.DAMAGE_DEALT, actor="adv_1"))
        bus.fire(make_event(EventType.DAMAGE_DEALT, actor="adv_2"))
        assert bus.count(EventType.DAMAGE_DEALT) == 3
        assert bus.count(EventType.DAMAGE_DEALT, actor_id="adv_1") == 2


class TestObservability:
    def test_dump_returns_list(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT, t=1.0, amount=30))
        dump = bus.dump()
        assert isinstance(dump, list)
        assert len(dump) == 1
        assert dump[0]["type"] == "DAMAGE_DEALT"
        assert dump[0]["data"]["amount"] == 30

    def test_dump_most_recent_first(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT, t=1.0))
        bus.fire(make_event(EventType.DAMAGE_DEALT, t=2.0))
        dump = bus.dump()
        assert dump[0]["t"] == pytest.approx(2.0)
        assert dump[1]["t"] == pytest.approx(1.0)

    def test_dump_limit(self):
        bus = EventBus()
        for i in range(10):
            bus.fire(make_event(EventType.DAMAGE_DEALT, t=float(i)))
        dump = bus.dump(limit=3)
        assert len(dump) == 3

    def test_summary(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT))
        bus.fire(make_event(EventType.DAMAGE_DEALT))
        bus.fire(make_event(EventType.TRAP_TRIGGERED))
        summary = bus.summary()
        assert summary["DAMAGE_DEALT"] == 2
        assert summary["TRAP_TRIGGERED"] == 1

    def test_repr(self):
        bus = EventBus()
        bus.fire(make_event(EventType.DAMAGE_DEALT))
        assert "1" in repr(bus)


class TestEventData:
    def test_data_dict_accessible(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.DAMAGE_DEALT, received.append)
        bus.fire(make_event(EventType.DAMAGE_DEALT, amount=25, source="spike"))
        assert received[0].data["amount"] == 25
        assert received[0].data["source"] == "spike"
