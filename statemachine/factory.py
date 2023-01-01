import warnings
from collections import OrderedDict

from . import registry
from .event import Event
from .exceptions import InvalidDefinition
from .utils import ugettext as _, check_state_factory
from .state import State
from .transition import Transition
from .transition_list import TransitionList


class StateMachineMetaclass(type):
    def __init__(cls, name, bases, attrs):
        super(StateMachineMetaclass, cls).__init__(name, bases, attrs)
        registry.register(cls)
        cls.states = []
        cls._events = OrderedDict()
        cls.states_map = {}
        cls.add_inherited(bases)
        cls.add_from_attributes(attrs)

        for state in cls.states:
            setattr(cls, "is_{}".format(state.identifier), check_state_factory(state))

        cls._set_initial_state()

    def _set_initial_state(cls):
        if not cls.states:
            return
        initials = [s for s in cls.states if s.initial]
        if len(initials) != 1:
            raise InvalidDefinition(
                _(
                    "There should be one and only one initial state. "
                    "Your currently have these: {!r}".format(initials)
                )
            )
        cls.initial_state = initials[0]

    def add_inherited(cls, bases):
        for base in bases:
            for state in getattr(base, "states", []):
                cls.add_state(state.identifier, state)

            events = getattr(base, "_events", {})
            for event in events.values():
                cls.add_event(event.name, event.transitions)

    def add_from_attributes(cls, attrs):
        for key, value in sorted(attrs.items(), key=lambda pair: pair[0]):
            if isinstance(value, State):
                cls.add_state(key, value)
            elif isinstance(value, (Transition, TransitionList)):
                cls.add_event(key, value)

    def add_state(cls, identifier, state):
        state._set_identifier(identifier)
        cls.states.append(state)
        cls.states_map[state.value] = state

    def add_event(cls, trigger, transitions):
        if trigger not in cls._events:
            event = Event(trigger)
            cls._events[trigger] = event
            setattr(cls, trigger, event)  # bind event to the class
        else:
            event = cls._events[trigger]

        event.add_transitions(transitions)
        return event

    @property
    def transitions(self):
        warnings.warn(
            "Class level property `transitions` is deprecated. Use `events` instead.",
            DeprecationWarning,
        )
        return self.events

    @property
    def events(self):
        return list(self._events.values())
