from statemachine.event import Event

from .utils import ensure_iterable


class Events:
    """A collection of event names."""

    def __init__(self):
        self._items = []

    def __repr__(self):
        sep = " " if len(self._items) > 1 else ""
        return sep.join(item for item in self._items)

    def __iter__(self):
        return iter(self._items)

    def add(self, events):
        if events is None:
            return self

        unprepared = ensure_iterable(events)
        for events in unprepared:
            for event in events.split(" "):
                if event in self._items:
                    continue
                self._items.append(Event(event))

        return self

    def match(self, event: str):
        return any(e == event for e in self)
