from .utils import ensure_iterable


class TransitionList:
    def __init__(self, transitions=None):
        self.transitions = list(transitions) if transitions else []

    def __repr__(self):
        return f"{type(self).__name__}({self.transitions!r})"

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

    def _add_callback(self, callback, name, is_event=False, **kwargs):
        for transition in self.transitions:
            list_obj = getattr(transition, name)
            list_obj._add_unbounded_callback(
                callback,
                is_event=is_event,
                transitions=self,
                **kwargs,
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

    def cond(self, f):
        return self._add_callback(f, "cond")

    def unless(self, f):
        return self._add_callback(f, "cond", expected_value=False)

    def validators(self, f):
        return self._add_callback(f, "validators")

    def add_event(self, event):
        for transition in self.transitions:
            transition.add_event(event)

    @property
    def unique_events(self):
        tmp_ordered_unique_events_as_keys_on_dict = {}
        for transition in self.transitions:
            for event in transition.events:
                tmp_ordered_unique_events_as_keys_on_dict[event] = True

        return list(tmp_ordered_unique_events_as_keys_on_dict.keys())
