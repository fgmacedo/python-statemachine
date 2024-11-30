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
        self._sentinel = object()
        self._rtc = rtc
        self._running = True
        self._init(sm)

    def _init(self, sm: "StateMachine"):
        self.sm: StateMachine = proxy(sm)
        self._external_queue: Queue = PriorityQueue()
        self._processing = Lock()

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        del state["_external_queue"]
        del state["_processing"]
        del state["sm"]
        return state

    def __setstate__(self, state: dict) -> None:
        for attr, value in state.items():
            setattr(self, attr, value)

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
