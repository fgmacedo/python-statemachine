import warnings
from collections import OrderedDict

from .callable_proxy import CallableInstance
from .event_data import EventData
from .exceptions import TransitionNotAllowed
from .transition_list import TransitionList
from .utils import ensure_iterable


class OrderedDefaultDict(OrderedDict):  # python <= 3.5 compat layer
    factory = TransitionList

    def __missing__(self, key):
        self[key] = value = self.factory()
        return value


class Event(object):
    def __init__(self, name):
        self.name = name
        self._transitions = OrderedDefaultDict()

    def __repr__(self):
        return "{}({!r}, {!r})".format(
            type(self).__name__, self.name, self._transitions
        )

    def __get__(self, machine, owner):
        def trigger_callback(*args, **kwargs):
            return self.trigger(machine, *args, **kwargs)

        return CallableInstance(self, func=trigger_callback)

    def __set__(self, instance, value):
        "does nothing (not allow overriding)"

    def add_transition(self, transition):
        transition.trigger = self.name
        self._transitions[transition.source].add_transitions(transition)

    def add_transitions(self, transitions):
        transitions = ensure_iterable(transitions)
        for transition in transitions:
            self.add_transition(transition)

    @property
    def identifier(self):
        warnings.warn(
            "identifier is deprecated. Use `name` instead", DeprecationWarning
        )
        return self.name

    @property
    def validators(self):
        return list(
            {
                validator
                for transition in self.transitions
                for validator in transition.validators
            }
        )

    @validators.setter
    def validators(self, value):
        for transition in self.transitions:
            transition.validators.add(value)

    @property
    def transitions(self):
        return [
            transition
            for transition_list in self._transitions.values()
            for transition in transition_list
        ]

    def _check_is_valid_source(self, state):
        if state not in self._transitions:
            raise TransitionNotAllowed(self, state)

    def trigger(self, machine, *args, **kwargs):
        event_data = EventData(machine, self, *args, **kwargs)

        def trigger_wrapper():
            """Wrapper that captures event_data as closure."""
            return self._trigger(event_data)

        return machine._process(trigger_wrapper)

    def _trigger(self, event_data):
        event_data.source = event_data.machine.current_state
        event_data.state = event_data.machine.current_state
        event_data.model = event_data.machine.model

        try:
            self._check_is_valid_source(event_data.state)
            self._process(event_data)
        except Exception as error:
            event_data.error = error
            # TODO: Log errors
            # TODO: Allow exception handlers
            raise
        return event_data.result

    def _process(self, event_data):
        for transition in self._transitions[event_data.state]:
            event_data.transition = transition
            if transition.execute(event_data):
                event_data.executed = True
                break
        else:
            raise TransitionNotAllowed(self, event_data.state)
