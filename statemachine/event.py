import asyncio
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

    async def trigger(self, machine: "StateMachine", *args, **kwargs):
        async def trigger_wrapper():
            """Wrapper that captures event_data as closure."""
            trigger_data = TriggerData(
                machine=machine,
                event=self.name,
                args=args,
                kwargs=kwargs,
            )
            return await self._trigger(trigger_data)

        return await machine._process(trigger_wrapper)

    async def _trigger(self, trigger_data: TriggerData):
        event_data = None
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


def trigger_event_factory(event_instance, is_async: bool = False):
    """Build a method that sends specific `event` to the machine"""

    def trigger_event(self, *args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        return loop.run_until_complete(event_instance.trigger(self, *args, **kwargs))

    async def async_trigger_event(self, *args, **kwargs):
        return await event_instance.trigger(self, *args, **kwargs)

    trigger_event.name = event_instance.name
    trigger_event.identifier = event_instance.name
    trigger_event._is_sm_event = True

    return async_trigger_event if is_async else trigger_event


def same_event_cond_builder(expected_event: str):
    """
    Builds a condition method that evaluates to ``True`` when the expected event is received.
    """

    def cond(event: str) -> bool:
        return event == expected_event

    return cond
