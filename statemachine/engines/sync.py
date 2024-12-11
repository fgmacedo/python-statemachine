import logging
from time import sleep
from time import time
from typing import TYPE_CHECKING

from statemachine.event import BoundEvent
from statemachine.orderedset import OrderedSet

from ..event_data import TriggerData
from ..exceptions import TransitionNotAllowed
from .base import BaseEngine

if TYPE_CHECKING:
    from ..transition import Transition

logger = logging.getLogger(__name__)


class SyncEngine(BaseEngine):
    def start(self):
        if self.sm.current_state_value is not None:
            return

        self.activate_initial_state()

    def activate_initial_state(self):
        """
        Activate the initial state.

        Called automatically on state machine creation from sync code, but in
        async code, the user must call this method explicitly.

        Given how async works on python, there's no built-in way to activate the initial state that
        may depend on async code from the StateMachine.__init__ method.
        """
        if self.sm.current_state_value is None:
            trigger_data = BoundEvent("__initial__", _sm=self.sm).build_trigger(machine=self.sm)
            transition = self._initial_transition(trigger_data)
            self._processing.acquire(blocking=False)
            try:
                self._enter_states([transition], trigger_data, {})
            finally:
                self._processing.release()
        return self.processing_loop()

    def processing_loop(self):  # noqa: C901
        """Process event triggers.

        The event is put on a queue, and only the first event will have the result collected.

        .. note::
            While processing the queue items, if others events are generated, they
            will be processed sequentially (and not nested).

        """
        # We make sure that only the first event enters the processing critical section,
        # next events will only be put on the queue and processed by the same loop.
        if not self._processing.acquire(blocking=False):
            return None

        # We will collect the first result as the processing result to keep backwards compatibility
        # so we need to use a sentinel object instead of `None` because the first result may
        # be also `None`, and on this case the `first_result` may be overridden by another result.
        logger.debug("Processing loop started: %s", self.sm.current_state_value)
        first_result = self._sentinel
        try:
            took_events = True
            while took_events:
                took_events = False
                # Execute the triggers in the queue in FIFO order until the queue is empty
                # while self._running and not self.external_queue.is_empty():
                macrostep_done = False
                enabled_transitions: "OrderedSet[Transition] | None" = None

                # handles eventless transitions and internal events
                while not macrostep_done:
                    internal_event = TriggerData(
                        self.sm, event=None
                    )  # this one is a "null object"
                    enabled_transitions = self.select_eventless_transitions(internal_event)
                    if not enabled_transitions:
                        if self.internal_queue.is_empty():
                            macrostep_done = True
                        else:
                            internal_event = self.internal_queue.pop()

                            enabled_transitions = self.select_transitions(internal_event)
                    if enabled_transitions:
                        logger.debug("Eventless/internal queue: %s", enabled_transitions)
                        took_events = True
                        self.microstep(list(enabled_transitions), internal_event)

                # TODO: Invoke platform-specific logic
                # for state in sorted(self.states_to_invoke, key=self.entry_order):
                #     for inv in sorted(state.invoke, key=self.document_order):
                #         self.invoke(inv)
                # self.states_to_invoke.clear()

                # Process remaining internal events before external events
                while not self.internal_queue.is_empty():
                    internal_event = self.internal_queue.pop()
                    enabled_transitions = self.select_transitions(internal_event)
                    if enabled_transitions:
                        self.microstep(list(enabled_transitions))

                # Process external events
                while not self.external_queue.is_empty():
                    took_events = True
                    external_event = self.external_queue.pop()
                    current_time = time()
                    if external_event.execution_time > current_time:
                        self.put(external_event)
                        sleep(0.001)
                        continue

                    logger.debug("External event: %s", external_event)
                    # # TODO: Handle cancel event
                    # if self.is_cancel_event(external_event):
                    #     self.running = False
                    #     return

                    # TODO: Invoke states
                    # for state in self.configuration:
                    #     for inv in state.invoke:
                    #         if inv.invokeid == external_event.invokeid:
                    #             self.apply_finalize(inv, external_event)
                    #         if inv.autoforward:
                    #             self.send(inv.id, external_event)

                    enabled_transitions = self.select_transitions(external_event)
                    logger.debug("Enabled transitions: %s", enabled_transitions)
                    if enabled_transitions:
                        try:
                            result = self.microstep(list(enabled_transitions), external_event)
                            if first_result is self._sentinel:
                                first_result = result

                        except Exception:
                            # Whe clear the queue as we don't have an expected behavior
                            # and cannot keep processing
                            self.clear()
                            raise

                    else:
                        if not self.sm.allow_event_without_transition:
                            raise TransitionNotAllowed(external_event.event, self.sm.configuration)

        finally:
            self._processing.release()
        return first_result if first_result is not self._sentinel else None
