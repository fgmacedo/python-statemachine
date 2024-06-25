from typing import TYPE_CHECKING

from statemachine.utils import run_async_from_sync

from .event_data import TriggerData

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

        return await machine._process(trigger_data)


def trigger_event_factory(event_instance: Event):
    """Build a method that sends specific `event` to the machine"""

    def trigger_event(self, *args, **kwargs):
        coro = event_instance.trigger(self, *args, **kwargs)
        return run_async_from_sync(coro)

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
