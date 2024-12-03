import heapq
from time import sleep
from time import time
from typing import TYPE_CHECKING

from ..event_data import EventData
from ..event_data import TriggerData
from ..exceptions import TransitionNotAllowed
from .base import BaseEngine

if TYPE_CHECKING:
    from ..transition import Transition


class SyncEngine(BaseEngine):
    def start(self):
        super().start()
        self.activate_initial_state()

    def activate_initial_state(self):
        """
        Activate the initial state.

        Called automatically on state machine creation from sync code, but in
        async code, the user must call this method explicitly.

        Given how async works on python, there's no built-in way to activate the initial state that
        may depend on async code from the StateMachine.__init__ method.
        """
        return self.processing_loop()

    def processing_loop(self):
        """Process event triggers.

        The simplest implementation is the non-RTC (synchronous),
        where the trigger will be run immediately and the result collected as the return.

        .. note::

            While processing the trigger, if others events are generated, they
            will also be processed immediately, so a "nested" behavior happens.

        If the machine is on ``rtc`` model (queued), the event is put on a queue, and only the
        first event will have the result collected.

        .. note::
            While processing the queue items, if others events are generated, they
            will be processed sequentially (and not nested).

        """
        if not self._rtc:
            # The machine is in "synchronous" mode
            trigger_data = heapq.heappop(self._external_queue)
            return self._trigger(trigger_data)

        # We make sure that only the first event enters the processing critical section,
        # next events will only be put on the queue and processed by the same loop.
        if not self._processing.acquire(blocking=False):
            return None

        # We will collect the first result as the processing result to keep backwards compatibility
        # so we need to use a sentinel object instead of `None` because the first result may
        # be also `None`, and on this case the `first_result` may be overridden by another result.
        first_result = self._sentinel
        try:
            # Execute the triggers in the queue in FIFO order until the queue is empty
            while self._running and self._external_queue:
                trigger_data = heapq.heappop(self._external_queue)
                current_time = time()
                if trigger_data.execution_time > current_time:
                    self.put(trigger_data)
                    sleep(0.001)
                    continue
                try:
                    result = self._trigger(trigger_data)
                    if first_result is self._sentinel:
                        first_result = result
                except Exception:
                    # Whe clear the queue as we don't have an expected behavior
                    # and cannot keep processing
                    self._external_queue.clear()
                    raise
        finally:
            self._processing.release()
        return first_result if first_result is not self._sentinel else None

    def _trigger(self, trigger_data: TriggerData):  # noqa: C901
        executed = False
        if trigger_data.event == "__initial__":
            transition = self._initial_transition(trigger_data)
            self._activate(trigger_data, transition)
            if self.sm.current_state.transitions.has_eventless_transition:
                self.put(TriggerData(self.sm, event=None))
            return self._sentinel

        state = self.sm.current_state
        for transition in state.transitions:
            if not transition.match(trigger_data.event):
                continue

            executed, result = self._activate(trigger_data, transition)
            if not executed:
                continue

            if self.sm.current_state.transitions.has_eventless_transition:
                self.put(TriggerData(self.sm, event=None))
            break
        else:
            if not self.sm.allow_event_without_transition:
                raise TransitionNotAllowed(trigger_data.event, state)

        return result if executed else None

    def _activate(self, trigger_data: TriggerData, transition: "Transition"):  # noqa: C901
        event_data = EventData(trigger_data=trigger_data, transition=transition)
        args, kwargs = event_data.args, event_data.extended_kwargs

        self.sm._callbacks.call(transition.validators.key, *args, **kwargs)
        if not self.sm._callbacks.all(transition.cond.key, *args, **kwargs):
            return False, None

        source = transition.source
        target = transition.target

        result = self.sm._callbacks.call(transition.before.key, *args, **kwargs)
        if source is not None and not transition.internal:
            self.sm._callbacks.call(source.exit.key, *args, **kwargs)

        result += self.sm._callbacks.call(transition.on.key, *args, **kwargs)

        self.sm.current_state = target
        event_data.state = target
        kwargs["state"] = target

        if not transition.internal:
            self.sm._callbacks.call(target.enter.key, *args, **kwargs)
        self.sm._callbacks.call(transition.after.key, *args, **kwargs)

        if target.final:
            self._external_queue.clear()
            self._running = False

        if len(result) == 0:
            result = None
        elif len(result) == 1:
            result = result[0]

        return True, result
