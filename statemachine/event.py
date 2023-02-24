from .event_data import EventData
from .event_data import TriggerData
from .exceptions import TransitionNotAllowed


class Event:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"{type(self).__name__}({self.name!r})"

    def __call__(self, machine, *args, **kwargs):
        return self.trigger(machine, *args, **kwargs)

    def trigger(self, machine, *args, **kwargs):
        def trigger_wrapper():
            """Wrapper that captures event_data as closure."""
            trigger_data = TriggerData(
                machine=machine,
                event=self.name,
                args=args,
                kwargs=kwargs,
            )
            return self._trigger(trigger_data)

        return machine._process(trigger_wrapper)

    def _trigger(self, trigger_data: TriggerData):
        event_data = self._process(trigger_data)
        return event_data.result

    def _process(self, trigger_data: TriggerData):
        state = trigger_data.machine.current_state
        for transition in state.transitions:
            if not transition.match(trigger_data.event):
                continue

            event_data = EventData(trigger_data=trigger_data, transition=transition)
            if transition.execute(event_data):
                event_data.executed = True
                break
        else:
            raise TransitionNotAllowed(trigger_data.event, state)

        return event_data


def trigger_event_factory(event):
    """Build a method that sends specific `event` to the machine"""
    event_instance = Event(event)

    def trigger_event(self, *args, **kwargs):
        return event_instance(self, *args, **kwargs)

    trigger_event.name = event
    trigger_event.identifier = event
    trigger_event._is_sm_event = True

    return trigger_event
