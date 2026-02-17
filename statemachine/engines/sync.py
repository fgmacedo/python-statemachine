import logging
from time import sleep
from time import time
from typing import TYPE_CHECKING

from statemachine.event import BoundEvent
from statemachine.orderedset import OrderedSet

from ..event_data import TriggerData
from ..exceptions import InvalidDefinition
from ..exceptions import TransitionNotAllowed
from .base import BaseEngine

if TYPE_CHECKING:
    from ..transition import Transition

logger = logging.getLogger(__name__)


class SyncEngine(BaseEngine):
    def _run_microstep(self, enabled_transitions, trigger_data):
        """Run a microstep for internal/eventless transitions with error handling.

        Note: microstep() handles its own errors internally, so this try/except
        is a safety net that is not expected to be reached in normal operation.
        """
        try:
            self.microstep(list(enabled_transitions), trigger_data)
        except InvalidDefinition:
            raise
        except Exception as e:  # pragma: no cover
            self._handle_error(e, trigger_data)

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
            transitions = self._initial_transitions(trigger_data)
            self._processing.acquire(blocking=False)
            try:
                self._enter_states(transitions, trigger_data, OrderedSet(), OrderedSet())
            finally:
                self._processing.release()
        return self.processing_loop()

    def processing_loop(self, caller_future=None):  # noqa: C901
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
            while took_events and not self.sm.is_terminated:
                self.clear_cache()
                took_events = False
                # Execute the triggers in the queue in FIFO order until the queue is empty
                # while self._running and not self.external_queue.is_empty():
                macrostep_done = False
                enabled_transitions: "OrderedSet[Transition] | None" = None

                # handles eventless transitions and internal events
                while not macrostep_done:
                    logger.debug("Macrostep: eventless/internal queue")

                    self.clear_cache()
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
                        logger.debug("Enabled transitions: %s", enabled_transitions)
                        took_events = True
                        self._run_microstep(enabled_transitions, internal_event)

                # Spawn invocations for states entered during this macrostep
                for state in sorted(
                    self.states_to_invoke,
                    key=lambda s: s.document_order,
                ):
                    for config in state.invocations:
                        self.invoke_manager.spawn_sync(state, config, internal_event)
                self.states_to_invoke.clear()

                # Process remaining internal events before external events.
                # Note: the macrostep loop above already drains the internal queue,
                # so this is a safety net per SCXML spec for invoke-generated events.
                while not self.internal_queue.is_empty():  # pragma: no cover
                    internal_event = self.internal_queue.pop()
                    enabled_transitions = self.select_transitions(internal_event)
                    if enabled_transitions:
                        self._run_microstep(enabled_transitions, internal_event)

                # Process external events
                logger.debug("Macrostep: external queue")
                while not self.external_queue.is_empty():
                    self.clear_cache()
                    took_events = True
                    external_event = self.external_queue.pop()
                    current_time = time()
                    if external_event.execution_time > current_time:
                        self.put(external_event, _delayed=True)
                        sleep(self.sm._loop_sleep_in_ms)
                        # Break to Phase 1 so internal events and eventless
                        # transitions can be processed while we wait.
                        break

                    # Forward delayed cross-session events to their target
                    if external_event.forward_target:
                        self._forward_to_target(external_event)
                        continue

                    logger.debug("External event: %s", external_event.event)

                    # Handle invoke finalize and autoforward
                    for state in self.sm.configuration:
                        for inv in self.invoke_manager.active_for_state(state):
                            if external_event.invokeid and inv.invokeid == external_event.invokeid:
                                self.invoke_manager.apply_finalize(inv, external_event)
                            if inv.config.autoforward and external_event.event:
                                self.invoke_manager.forward_event(
                                    inv, str(external_event.event), external_event
                                )

                    enabled_transitions = self.select_transitions(external_event)
                    logger.debug("Enabled transitions: %s", enabled_transitions)
                    if enabled_transitions:
                        try:
                            result = self.microstep(list(enabled_transitions), external_event)
                            if first_result is self._sentinel:
                                first_result = result

                        except Exception:
                            # We clear the queue as we don't have an expected behavior
                            # and cannot keep processing
                            self.clear()
                            raise

                        # Per SCXML spec: process ONE external event per macrostep,
                        # then loop back to handle eventless transitions, internal
                        # events, and invoke spawning before the next external event.
                        break

                    else:
                        if not self.sm.allow_event_without_transition:
                            raise TransitionNotAllowed(external_event.event, self.sm.configuration)

                # If no events were processed but there are pending events
                # on the external queue (e.g., delayed timeouts in SCXML tests),
                # keep the loop alive so child sessions can send events back.
                if not took_events and not self.external_queue.is_empty():
                    took_events = True

        finally:
            self._processing.release()
        return first_result if first_result is not self._sentinel else None

    def enabled_events(self, *args, **kwargs):
        sm = self.sm
        enabled = {}
        for state in sm.configuration:
            for transition in state.transitions:
                for event in transition.events:
                    if event in enabled:
                        continue
                    extended_kwargs = kwargs.copy()
                    extended_kwargs.update(
                        {
                            "machine": sm,
                            "model": sm.model,
                            "event": getattr(sm, event),
                            "source": transition.source,
                            "target": transition.target,
                            "state": state,
                            "transition": transition,
                        }
                    )
                    try:
                        if sm._callbacks.all(transition.cond.key, *args, **extended_kwargs):
                            enabled[event] = getattr(sm, event)
                    except Exception:
                        enabled[event] = getattr(sm, event)
        return list(enabled.values())
