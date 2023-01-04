from collections import OrderedDict
from uuid import uuid4

from .utils import ensure_iterable


class TransitionList(object):
    def __init__(self, *transitions):
        self.transitions = list(*transitions)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.transitions)

    def __or__(self, other):
        self.add_transitions(other)
        return self

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

    def __call__(self, f):
        """`TransitionList` was called as decorator `@<event> = <transitions>` syntax.

        This results in a colision of names, because the event trigger and the given `f`
        callback cannot share the same attribute name on the class.

        And if we assign ``f`` directly as callback on the ``transitions.before`` list,
        this will result in an `unbounded method error`, with `f` expecting a parameter
        ``self`` not defined.

        The implemented solution is to resolve the colision giving the callback an unique
        name. On the :func:`StateMachineMetaclass.add_from_attributes` the method
        will be bounded to the class with his unique name ``_callback_attr``.

        Args:

            f (callable): The decorated method to add as a callback before the transitions
                occurs.

        """
        f._is_event = True
        f._callback_attr = "_before_{}".format(uuid4().hex)
        f._transitions = self
        for transition in self.transitions:
            transition.before.add(f._callback_attr)
        return f

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
