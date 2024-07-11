from collections import deque
from threading import Lock
from typing import TYPE_CHECKING
from weakref import proxy

from ..event_data import TriggerData

if TYPE_CHECKING:
    from ..statemachine import StateMachine


class BaseEngine:
    def __init__(self, sm: "StateMachine", rtc: bool = True) -> None:
        self.sm = proxy(sm)
        self._external_queue: deque = deque()
        self._sentinel = object()
        self._rtc = rtc
        self._processing = Lock()
        self._put_initial_activation_trigger_on_queue()

    def _put_nonblocking(self, trigger_data: TriggerData):
        """Put the trigger on the queue without blocking the caller."""
        self._external_queue.append(trigger_data)

    def _put_initial_activation_trigger_on_queue(self):
        # Activate the initial state, this only works if the outer scope is sync code.
        # for async code, the user should manually call `await sm.activate_initial_state()`
        # after state machine creation.
        if self.sm.current_state_value is None:
            trigger_data = TriggerData(
                machine=self.sm,
                event="__initial__",
            )
            self._put_nonblocking(trigger_data)
