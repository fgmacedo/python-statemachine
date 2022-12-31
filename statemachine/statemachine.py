# coding: utf-8

import warnings
from collections import OrderedDict

from typing import Any, List, Dict, Optional

from . import registry
from .event import Event
from .exceptions import (
    InvalidDefinition,
    InvalidStateValue,
    InvalidTransitionIdentifier,
)
from .graph import visit_connected_states
from .model import Model
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


class BaseStateMachine(object):

    _events = {}  # type: Dict[Any, Any]
    states = []  # type: List[State]
    states_map = {}  # type: Dict[Any, State]

    def __init__(self, model=None, state_field="state", start_value=None):
        self.model = model if model else Model()
        self.state_field = state_field
        self.start_value = start_value

        self.check()

    def __repr__(self):
        return "{}(model={!r}, state_field={!r}, current_state={!r})".format(
            type(self).__name__,
            self.model,
            self.state_field,
            self.current_state.identifier,
        )

    def _disconnected_states(self, starting_state):
        visitable_states = set(visit_connected_states(starting_state))
        return set(self.states) - visitable_states

    def _check_states_and_transitions(self):
        for state in self.states:
            state.setup(self)
            for transition in state.transitions:
                transition.setup(self)

    def _activate_initial_state(self, initials):

        current_state_value = (
            self.start_value if self.start_value else self.initial_state.value
        )
        if self.current_state_value is None:

            try:
                initial_state = self.states_map[current_state_value]
            except KeyError:
                raise InvalidStateValue(current_state_value)

            # trigger an one-time event `__initial__` to enter the current state.
            # current_state = self.current_state
            event = Event("__initial__")
            transition = Transition(None, initial_state)
            transition.setup(self)
            transition.before.clear()
            transition.after.clear()
            event.add_transition(transition)
            event.trigger(self)

    def check(self):
        if not self.states:
            raise InvalidDefinition(_("There are no states."))

        if not self._events:
            raise InvalidDefinition(_("There are no events."))

        initials = [s for s in self.states if s.initial]
        if len(initials) != 1:
            raise InvalidDefinition(
                _(
                    "There should be one and only one initial state. "
                    "Your currently have these: {!r}".format(initials)
                )
            )
        self.initial_state = initials[0]

        disconnected_states = self._disconnected_states(self.initial_state)
        if disconnected_states:
            raise InvalidDefinition(
                _(
                    "There are unreachable states. "
                    "The statemachine graph should have a single component. "
                    "Disconnected states: [{}]".format(disconnected_states)
                )
            )

        self._check_states_and_transitions()

        final_state_with_invalid_transitions = [
            state for state in self.final_states if state.transitions
        ]

        if final_state_with_invalid_transitions:
            raise InvalidDefinition(
                _(
                    "Final state does not should have defined "
                    "transitions starting from that state"
                )
            )

        self._activate_initial_state(initials)

    @property
    def final_states(self):
        return [state for state in self.states if state.final]

    @property
    def current_state_value(self):
        value = getattr(self.model, self.state_field, None)
        return value

    @current_state_value.setter
    def current_state_value(self, value):
        if value not in self.states_map:
            raise InvalidStateValue(value)
        setattr(self.model, self.state_field, value)

    @property
    def current_state(self):
        # type: () -> Optional[State]
        return self.states_map.get(self.current_state_value, None)

    @current_state.setter
    def current_state(self, value):
        self.current_state_value = value.value

    @property
    def transitions(self):
        warnings.warn(
            "Property `transitions` is deprecated. Use `events` instead.",
            DeprecationWarning,
        )
        return self.events

    @property
    def events(self):
        return self.__class__.transitions

    @property
    def allowed_transitions(self):
        "get the callable proxy of the current allowed transitions"
        return [getattr(self, t.trigger) for t in self.current_state.transitions]

    def _process(self, trigger):
        """This method will also handle execution queue"""
        return trigger()

    def _activate(self, event_data):
        transition = event_data.transition
        source = event_data.state
        destination = transition.destination

        result = transition.before(*event_data.args, **event_data.extended_kwargs)
        if source is not None:
            source.exit(*event_data.args, **event_data.extended_kwargs)

        self.current_state = destination

        event_data.state = destination
        destination.enter(*event_data.args, **event_data.extended_kwargs)
        transition.after(*event_data.args, **event_data.extended_kwargs)

        if len(result) == 0:
            result = None
        elif len(result) == 1:
            result = result[0]

        return result

    def get_event(self, trigger):
        event = getattr(self, trigger, None)
        if trigger not in self._events or event is None:
            raise InvalidTransitionIdentifier(trigger)
        return event

    def run(self, trigger, *args, **kwargs):
        event = self.get_event(trigger)
        return event(*args, **kwargs)


StateMachine = StateMachineMetaclass("StateMachine", (BaseStateMachine,), {})
