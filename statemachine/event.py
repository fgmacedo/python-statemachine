import warnings
from collections import OrderedDict

from .callable_proxy import CallableInstance
from .event_data import EventData
from .exceptions import TransitionNotAllowed, InvalidDefinition
from .transition_list import TransitionList


class OrderedDefaultDict(OrderedDict):  # python <= 3.5 compat layer
    factory = TransitionList

    def __missing__(self, key):
        self[key] = value = self.factory()
        return value


class Event(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "{}({!r})".format(
            type(self).__name__, self.name
        )

    def __get__(self, machine, owner):
        def trigger_callback(*args, **kwargs):
            return self.trigger(machine, *args, **kwargs)

        return CallableInstance(self, func=trigger_callback)

    def __set__(self, instance, value):
        "does nothing (not allow overriding)"

    def __call__(self, machine, *args, **kwargs):
        return self.trigger(machine, *args, **kwargs)

    def trigger(self, machine, *args, **kwargs):
        event_data = EventData(machine, self.name, *args, **kwargs)

        def trigger_wrapper():
            """Wrapper that captures event_data as closure."""
            return self._trigger(event_data)

        return machine._process(trigger_wrapper)

    def _trigger(self, event_data):
        event_data.source = event_data.machine.current_state
        event_data.state = event_data.machine.current_state
        event_data.model = event_data.machine.model

        try:
            self._process(event_data)
        except Exception as error:
            event_data.error = error
            # TODO: Log errors
            # TODO: Allow exception handlers
            raise
        return event_data.result

    def _process(self, event_data):
        for transition in event_data.source.transitions:
            if not transition.match(event_data.event):
                continue
            event_data.transition = transition
            if transition.execute(event_data):
                event_data.executed = True
                break
        else:
            raise TransitionNotAllowed(event_data.event, event_data.state)

    @property
    def identifier(self):
        warnings.warn(
            "identifier is deprecated. Use `name` instead", DeprecationWarning
        )
        return self.name

    @property
    def validators(self):
        warnings.warn(
            "validators from `Event` is deprecated. Use at machine", DeprecationWarning
        )
        return []

    @validators.setter
    def validators(self, value):
        raise InvalidDefinition("Cannot assign a validator from an event")
