from collections.abc import Callable
from itertools import chain
from time import monotonic
from time import sleep

from statemachine.event import BoundEvent
from statemachine.orderedset import OrderedSet

from ..event_data import TriggerData
from ..exceptions import InvalidDefinition
from ..exceptions import TransitionNotAllowed
from ..state import State
from ..transition import Transition
from .base import BaseEngine
from .base import _processing_step


class SyncEngine(BaseEngine):
    def start(self, **kwargs):
        if self.sm.current_state_value is not None:
            return

        self.activate_initial_state(**kwargs)

    def activate_initial_state(self, **kwargs):
        """
        Activate the initial state.

        Called automatically on state machine creation from sync code, but in
        async code, the user must call this method explicitly.

        Given how async works on python, there's no built-in way to activate the initial state that
        may depend on async code from the StateMachine.__init__ method.
        """
        if self.sm.current_state_value is None:
            trigger_data = BoundEvent("__initial__", _sm=self.sm).build_trigger(
                machine=self.sm, **kwargs
            )
            transitions = self._initial_transitions(trigger_data)
            self._processing.acquire(blocking=False)
            try:
                with _processing_step(self):
                    self._enter_states(transitions, trigger_data, OrderedSet(), OrderedSet())
            finally:
                self._processing.release()
        return self.processing_loop()

    def processing_loop(self):
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
        self._debug("%s Processing loop started: %s", self._log_id, self.sm.current_state_value)
        first_result = self._sentinel
        try:
            with _processing_step(self):
                took_events = True
                while took_events and self.running:
                    self.clear_cache()
                    try:
                        took_events = self._run_macrostep()
                        # Spawn invoke handlers for states entered during this macrostep.
                        self._invoke_manager.spawn_pending_sync()
                    except Exception:
                        self.clear()
                        raise
                    self._check_root_final_state()
                    if not self.running:
                        break

                    took_external_events, first_result = self._take_due_external_event(
                        first_result
                    )
                    took_events = took_events or took_external_events

                if not self.running:
                    self._drop_external_events()
        finally:
            self._processing.release()
        self._debug("%s Processing loop ended", self._log_id)
        return first_result if first_result is not self._sentinel else None

    def _run_macrostep(self) -> bool:
        """Take eventless transitions and internal events until neither enables a transition.

        Returns whether any transition was taken. The internal queue is empty on return.
        """
        took_events = False
        while True:
            self._microstep_count = 0
            self._debug(
                "%s Macrostep %d: eventless/internal queue",
                self._log_id,
                self._macrostep_count,
            )

            self.clear_cache()
            internal_event = TriggerData(self.sm, event=None)  # this one is a "null object"
            enabled_transitions = self.select_eventless_transitions(internal_event)
            if not enabled_transitions:
                if self.internal_queue.is_empty():
                    return took_events
                internal_event = self.internal_queue.pop()
                enabled_transitions = self.select_transitions(internal_event)
            if enabled_transitions:
                self._debug("%s Enabled transitions: %s", self._log_id, enabled_transitions)
                took_events = True
                self.microstep(list(enabled_transitions), internal_event)

    def _take_due_external_event(self, first_result):
        """Take the external event at the head of the queue, if it is due.

        One at a time, so the macrostep that follows runs the internal events and eventless
        transitions it enabled before the next external event is taken.

        Returns whether the queue held an event, and ``first_result`` updated with the result
        of the first event that enabled a transition.
        """
        self._debug("%s Macrostep %d: external queue", self._log_id, self._macrostep_count)
        if self.external_queue.is_empty():
            return False, first_result

        self.clear_cache()
        external_event = self.external_queue.pop_due(monotonic())
        if external_event is None:
            sleep(self.sm._loop_sleep_in_ms)
            return True, first_result

        self._macrostep_count += 1
        self._microstep_count = 0
        self._debug(
            "%s macrostep %d: event=%s",
            self._log_id,
            self._macrostep_count,
            external_event.event,
        )

        result = self._take_external_event(external_event)
        if first_result is self._sentinel:
            first_result = result
        return True, first_result

    def _take_external_event(self, external_event: TriggerData):
        """Run one external event.

        Returns the event's microstep result, or the sentinel when it enabled no transition.
        """
        # Finalize + autoforward for active invocations
        self._invoke_manager.handle_external_event(external_event)

        enabled_transitions = self.select_transitions(external_event)
        self._debug("%s Enabled transitions: %s", self._log_id, enabled_transitions)
        if not enabled_transitions:
            if not self.sm.allow_event_without_transition:
                raise TransitionNotAllowed(external_event.event, self.sm.configuration)
            return self._sentinel

        try:
            return self.microstep(list(enabled_transitions), external_event)
        except Exception:
            # We clear the queue as we don't have an expected behavior
            # and cannot keep processing
            self.clear()
            raise

    def select_eventless_transitions(self, trigger_data: TriggerData):
        """
        Select the eventless transitions that match the trigger data.
        """
        return self._select_transitions(trigger_data, lambda t, _e: t.is_eventless)

    def select_transitions(self, trigger_data: TriggerData) -> OrderedSet[Transition]:
        """
        Select the transitions that match the trigger data.
        """
        return self._select_transitions(trigger_data, lambda t, e: t.match(e))

    def _first_transition_that_matches(
        self,
        state: State,
        trigger_data: TriggerData,
        predicate: Callable,
    ) -> "Transition | None":
        for s in chain([state], state.ancestors()):
            transition: Transition
            for transition in s.transitions:
                if (
                    not transition.initial
                    and predicate(transition, trigger_data.event)
                    and self._conditions_match(transition, trigger_data)
                ):
                    return transition
        return None

    def _select_transitions(
        self, trigger_data: TriggerData, predicate: Callable
    ) -> OrderedSet[Transition]:
        """Select the transitions that match the trigger data."""
        enabled_transitions = OrderedSet[Transition]()

        # Get atomic states, TODO: sorted by document order
        atomic_states = (state for state in self.sm.configuration if state.is_atomic)

        for state in atomic_states:
            transition = self._first_transition_that_matches(state, trigger_data, predicate)
            if transition is not None:
                enabled_transitions.add(transition)

        return self._filter_conflicting_transitions(enabled_transitions)

    def microstep(self, transitions: list[Transition], trigger_data: TriggerData):
        """Process a single set of transitions in a 'lock step'.
        This includes exiting states, executing transition content, and entering states.
        """
        self._microstep_count += 1
        self._debug(
            "%s macro:%d micro:%d transitions: %s",
            self._log_id,
            self._macrostep_count,
            self._microstep_count,
            transitions,
        )
        previous_configuration = self.sm.configuration
        try:
            result = self._execute_transition_content(
                transitions, trigger_data, lambda t: t.before.key
            )

            states_to_exit = self._exit_states(transitions, trigger_data)
            result += self._enter_states(
                transitions, trigger_data, states_to_exit, previous_configuration
            )
        except InvalidDefinition:
            self.sm.configuration = previous_configuration
            raise
        except Exception as e:
            self.sm.configuration = previous_configuration
            self._handle_error(e, trigger_data)
            return None

        try:
            self._execute_transition_content(
                transitions,
                trigger_data,
                lambda t: t.after.key,
                set_target_as_state=True,
            )
        except InvalidDefinition:
            raise
        except Exception as e:
            self._handle_error(e, trigger_data)

        if len(result) == 0:
            result = None
        elif len(result) == 1:
            result = result[0]

        return result

    def _exit_states(
        self, enabled_transitions: list[Transition], trigger_data: TriggerData
    ) -> OrderedSet[State]:
        """Compute and process the states to exit for the given transitions."""
        ordered_states, result = self._prepare_exit_states(enabled_transitions)
        on_error = self._on_error_handler()

        for info in ordered_states:
            # Cancel invocations for this state before executing exit handlers.
            self._invoke_manager.cancel_for_state(info.state)

            args, kwargs = self._get_args_kwargs(info.transition, trigger_data, source=info.state)

            # Execute `onexit` handlers — same per-block error isolation as onentry.
            self._debug("%s Exiting state: %s", self._log_id, info.state)
            self.sm._callbacks.call(info.state.exit.key, *args, on_error=on_error, **kwargs)

            self._remove_state_from_configuration(info.state)

        return result

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
