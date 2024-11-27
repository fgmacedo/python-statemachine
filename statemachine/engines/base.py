import heapq
from threading import Lock
from typing import TYPE_CHECKING
from weakref import proxy

from ..event import BoundEvent
from ..event_data import TriggerData
from ..exceptions import TransitionNotAllowed
from ..state import State
from ..transition import Transition

if TYPE_CHECKING:
    from ..statemachine import StateMachine


class BaseEngine:
    def __init__(self, sm: "StateMachine", rtc: bool = True):
        self.sm: StateMachine = proxy(sm)
        self._external_queue: list = []
        self._sentinel = object()
        self._rtc = rtc
        self._processing = Lock()
        self._running = True

    def put(self, trigger_data: TriggerData):
        """Put the trigger on the queue without blocking the caller."""
        if not self._running and not self.sm.allow_event_without_transition:
            raise TransitionNotAllowed(trigger_data.event, self.sm.current_state)

        heapq.heappush(self._external_queue, trigger_data)

    def start(self):
        if self.sm.current_state_value is not None:
            return

        trigger_data = TriggerData(
            machine=self.sm,
            event=BoundEvent("__initial__", _sm=self.sm),
        )
        self.put(trigger_data)

    def _initial_transition(self, trigger_data):
        transition = Transition(State(), self.sm._get_initial_state(), event="__initial__")
        transition._specs.clear()
        return transition
