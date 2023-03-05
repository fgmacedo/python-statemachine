from typing import TYPE_CHECKING

from .event_data import EventData
from .event_data import TriggerData
from .exceptions import TransitionNotAllowed

if TYPE_CHECKING:
    from .statemachine import StateMachine


class Event:
    def __init__(self, name: str):
        self.name: str = name

    def __repr__(self):
        return f"{type(self).__name__}({self.name!r})"

    def trigger(self, machine: "StateMachine", *args, **kwargs):
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
        event_data = None
        state = trigger_data.machine.current_state
        for transition in state.transitions:
            if not transition.match(trigger_data.event):
                continue

            event_data = EventData(trigger_data=trigger_data, transition=transition)
            if transition.execute(event_data):
                event_data.executed = True
                break
        else:
            if not trigger_data.machine.allow_event_without_transition:
                raise TransitionNotAllowed(trigger_data.event, state)

        return event_data.result if event_data else None


def trigger_event_factory(event):
    """Build a method that sends specific `event` to the machine"""
    event_instance = Event(event)

    def trigger_event(self, *args, **kwargs):
        return event_instance.trigger(self, *args, **kwargs)

    trigger_event.name = event
    trigger_event.identifier = event
    trigger_event._is_sm_event = True

    return trigger_event


def same_event_cond_builder(expected_event: str):
    """
    Builds a condition method that evaluates to ``True`` when the expected event is received.
    """

    def cond(event: str) -> bool:
        return event == expected_event

    return cond
