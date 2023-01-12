from collections import OrderedDict

from .utils import ensure_iterable


class TransitionList(object):
    def __init__(self, transitions=None):
        self.transitions = list(transitions) if transitions else []

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.transitions)

    def __or__(self, other):
        return TransitionList(self.transitions).add_transitions(other)

    def add_transitions(self, transition):
        if isinstance(transition, TransitionList):
            transition = transition.transitions
        transitions = ensure_iterable(transition)

        for transition in transitions:
            self.transitions.append(transition)

        return self

    def __getitem__(self, index):
        return self.transitions[index]

    def __len__(self):
        return len(self.transitions)

    def _add_callback(self, callback, name, is_event=False):
        for transition in self.transitions:
            list_obj = getattr(transition, name)
            list_obj._add_unbounded_callback(
                callback,
                is_event=is_event,
                transitions=self,
            )
        return callback

    def __call__(self, f):
        return self._add_callback(f, "on", is_event=True)

    def before(self, f):
        return self._add_callback(f, "before")

    def after(self, f):
        return self._add_callback(f, "after")

    def on(self, f):
        return self._add_callback(f, "on")

    def add_event(self, event):
        for transition in self.transitions:
            transition.add_event(event)

    @property
    def unique_events(self):
        # Compat Python2.7: Using OrderedDict to get a unique ordered list
        tmp_list = OrderedDict()
        for transition in self.transitions:
            for event in transition.events:
                tmp_list[event] = True

        return list(tmp_list.keys())
