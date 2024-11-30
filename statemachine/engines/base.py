from queue import PriorityQueue
from queue import Queue
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
        self._external_queue: Queue = PriorityQueue()
        self._sentinel = object()
        self._rtc = rtc
        self._running = True
        self._processing = Lock()

    def empty(self):
        return self._external_queue.qsize() == 0

    def put(self, trigger_data: TriggerData):
        """Put the trigger on the queue without blocking the caller."""
        if not self._running and not self.sm.allow_event_without_transition:
            raise TransitionNotAllowed(trigger_data.event, self.sm.current_state)

        self._external_queue.put(trigger_data)

    def pop(self):
        try:
            return self._external_queue.get(block=False)
        except Exception:
            return None

    def clear(self):
        with self._external_queue.mutex:
            self._external_queue.queue.clear()

    def cancel_event(self, send_id: str):
        """Cancel the event with the given send_id."""

        # We use the internal `queue` to make thins faster as the mutex
        # is protecting the block below
        with self._external_queue.mutex:
            self._external_queue.queue = [
                trigger_data
                for trigger_data in self._external_queue.queue
                if trigger_data.send_id != send_id
            ]

    def start(self):
        if self.sm.current_state_value is not None:
            return

        BoundEvent("__initial__", _sm=self.sm).put(machine=self.sm)

    def _initial_transition(self, trigger_data):
        transition = Transition(State(), self.sm._get_initial_state(), event="__initial__")
        transition._specs.clear()
        return transition
