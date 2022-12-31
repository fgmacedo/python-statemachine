# coding: utf-8
from typing import Any, Optional, Text

from .callbacks import Callbacks, resolver_factory
from .transition_list import TransitionList
from .transition import Transition


class State(object):
    """
    A state in a state machine describes a particular behaviour of the machine.
    When we say that a machine is “in” a state, it means that the machine behaves
    in the way that state describes.
    """

    def __init__(
        self, name, value=None, initial=False, final=False, enter=None, exit=None
    ):
        # type: (Text, Optional[Any], bool, bool, Optional[Any], Optional[Any]) -> None
        self.name = name
        self.value = value
        self._initial = initial
        self.identifier = None  # type: Optional[Text]
        self.transitions = TransitionList()
        self._final = final
        self.enter = Callbacks().add(enter)
        self.exit = Callbacks().add(exit)

    def setup(self, machine):
        resolver = resolver_factory(machine, machine.model)
        self.enter.setup(resolver)
        self.exit.setup(resolver)

        self.enter.add(
            ["on_enter_state", "on_enter_{}".format(self.identifier)],
            suppress_errors=True,
        )
        self.exit.add(
            ["on_exit_state", "on_exit_{}".format(self.identifier)],
            suppress_errors=True,
        )

    def __repr__(self):
        return "{}({!r}, identifier={!r}, value={!r}, initial={!r}, final={!r})".format(
            type(self).__name__,
            self.name,
            self.identifier,
            self.value,
            self.initial,
            self.final,
        )

    def __get__(self, machine, owner):
        return self

    def __set__(self, instance, value):
        "does nothing (not allow overriding)"

    def _set_identifier(self, identifier):
        self.identifier = identifier
        if self.value is None:
            self.value = identifier

    def _to_(self, *states, **kwargs):
        transitions = TransitionList(
            Transition(self, state, **kwargs) for state in states
        )
        self.transitions.add_transitions(transitions)
        return transitions

    def _from_(self, *states, **kwargs):
        transitions = TransitionList()
        for origin in states:
            transition = Transition(origin, self, **kwargs)
            origin.transitions.add_transitions(transition)
            transitions.add_transitions(transition)
        return transitions

    def _get_proxy_method_to_itself(self, method):
        def proxy(*states, **kwargs):
            return method(*states, **kwargs)

        def proxy_to_itself(**kwargs):
            return proxy(self, **kwargs)

        proxy.itself = proxy_to_itself
        return proxy

    @property
    def to(self):
        """Create transitions to the given destination states.

        .. code::

            <origin_state>.to(*<destination_state>)

        """
        return self._get_proxy_method_to_itself(self._to_)

    @property
    def from_(self):
        return self._get_proxy_method_to_itself(self._from_)

    @property
    def initial(self):
        return self._initial

    @property
    def final(self):
        return self._final
