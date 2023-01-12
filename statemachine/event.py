import warnings

from .event_data import EventData
from .exceptions import TransitionNotAllowed


class Event(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.name)

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
            event_data._set_transition(transition)
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


def trigger_event_factory(event):
    """Build a method that sends specific `event` to the machine"""
    event_instance = Event(event)

    def trigger_event(self, *args, **kwargs):
        return event_instance(self, *args, **kwargs)

    trigger_event.name = event
    trigger_event.identifier = event

    return trigger_event
