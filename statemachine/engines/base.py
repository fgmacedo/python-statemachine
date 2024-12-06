from itertools import chain
from queue import PriorityQueue
from queue import Queue
from threading import Lock
from typing import TYPE_CHECKING
from weakref import proxy

from statemachine.orderedset import OrderedSet

from ..event import BoundEvent
from ..event_data import EventData
from ..event_data import TriggerData
from ..exceptions import TransitionNotAllowed
from ..state import State
from ..transition import Transition

if TYPE_CHECKING:
    from ..statemachine import StateMachine


class EventQueue:
    def __init__(self):
        self.queue: Queue = PriorityQueue()

    def empty(self):
        return self.queue.qsize() == 0

    def put(self, trigger_data: TriggerData):
        """Put the trigger on the queue without blocking the caller."""
        self.queue.put(trigger_data)

    def pop(self):
        """Pop a trigger from the queue without blocking the caller."""
        return self.queue.get(block=False)

    def clear(self):
        with self.queue.mutex:
            self.queue.queue.clear()

    def remove(self, send_id: str):
        # We use the internal `queue` to make thins faster as the mutex
        # is protecting the block below
        with self.queue.mutex:
            self.queue.queue = [
                trigger_data
                for trigger_data in self.queue.queue
                if trigger_data.send_id != send_id
            ]


class BaseEngine:
    def __init__(self, sm: "StateMachine"):
        self.sm: StateMachine = proxy(sm)
        self.external_queue = EventQueue()
        self.internal_queue = EventQueue()
        self._sentinel = object()
        self._running = True
        self._processing = Lock()

    def empty(self):
        return self.external_queue.empty()

    def put(self, trigger_data: TriggerData):
        """Put the trigger on the queue without blocking the caller."""
        if not self._running and not self.sm.allow_event_without_transition:
            raise TransitionNotAllowed(trigger_data.event, self.sm.current_state)

        self.external_queue.put(trigger_data)

    def pop(self):
        return self.external_queue.pop()

    def clear(self):
        self.external_queue.clear()

    def cancel_event(self, send_id: str):
        """Cancel the event with the given send_id."""
        self.external_queue.remove(send_id)

    def start(self):
        if self.sm.current_state_value is not None:
            return

        BoundEvent("__initial__", _sm=self.sm).put(machine=self.sm)

    def _initial_transition(self, trigger_data):
        transition = Transition(State(), self.sm._get_initial_state(), event="__initial__")
        transition._specs.clear()
        return transition
