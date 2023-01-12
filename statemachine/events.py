# coding: utf-8
from .utils import ensure_iterable


class Events(object):
    """A collection of event names."""

    def __init__(self):
        self.items = []

    def __repr__(self):
        sep = " " if len(self.items) > 1 else ""
        return sep.join(item for item in self.items)

    def __iter__(self):
        return iter(self.items)

    def add(self, events):
        if events is None:
            return self

        unprepared = ensure_iterable(events)
        for events in unprepared:
            for event in events.split(" "):
                if event in self.items:
                    continue
                self.items.append(event)

        return self

    def match(self, event):
        return any(t == event for t in self)
