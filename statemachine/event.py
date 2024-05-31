from functools import partial
from typing import TYPE_CHECKING

from statemachine.utils import run_async_from_sync

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

    async def trigger(self, machine: "StateMachine", *args, **kwargs):
        trigger_data = TriggerData(
            machine=machine,
            event=self.name,
            args=args,
            kwargs=kwargs,
        )
        trigger_wrapper = partial(self._trigger, trigger_data=trigger_data)

        return await machine._process(trigger_wrapper)

    async def _trigger(self, trigger_data: TriggerData):
        event_data = None
        await trigger_data.machine._ensure_is_initialized()

        state = trigger_data.machine.current_state
        for transition in state.transitions:
            if not transition.match(trigger_data.event):
                continue

            event_data = EventData(trigger_data=trigger_data, transition=transition)
            if await transition.execute(event_data):
                event_data.executed = True
                break
        else:
            if not trigger_data.machine.allow_event_without_transition:
                raise TransitionNotAllowed(trigger_data.event, state)

        return event_data.result if event_data else None


def trigger_event_factory(event_instance: Event):
    """Build a method that sends specific `event` to the machine"""

    def trigger_event(self, *args, **kwargs):
        return run_async_from_sync(event_instance.trigger(self, *args, **kwargs))

    trigger_event.name = event_instance.name  # type: ignore[attr-defined]
    trigger_event.identifier = event_instance.name  # type: ignore[attr-defined]
    trigger_event._is_sm_event = True  # type: ignore[attr-defined]
    return trigger_event


def same_event_cond_builder(expected_event: str):
    """
    Builds a condition method that evaluates to ``True`` when the expected event is received.
    """

    def cond(event: str) -> bool:
        return event == expected_event

    return cond
