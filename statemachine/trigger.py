# coding: utf-8

from .utils import ensure_iterable


class Triggers(object):

    def __init__(self):
        self.items = []

    def __repr__(self):
        sep = ', ' if len(self.items) > 1 else ''
        return sep.join(item for item in self.items)

    def __iter__(self):
        return iter(self.items)

    def add(self, triggers):
        if triggers is None:
            return self

        unprepared = ensure_iterable(triggers)
        for trigger in unprepared:
            if trigger in self.items:
                continue
            self.items.append(trigger)

        return self

    def match(self, event):
        return any(t == event for t in self)
