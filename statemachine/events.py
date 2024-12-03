from .event import Event
from .utils import ensure_iterable


class Events:
    """A collection of event names."""

    def __init__(self):
        self._items: list[Event] = []

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
                if isinstance(event, Event):
                    self._items.append(event)
                else:
                    self._items.append(Event(id=event, name=event))

        return self

    def match(self, event: str):
        return any(e == event for e in self)

    def _replace(self, old, new):
        self._items.remove(old)
        self._items.append(new)
