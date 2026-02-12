import asyncio
import logging
from itertools import chain
from time import time
from typing import TYPE_CHECKING
from typing import Callable
from typing import List

from ..event_data import EventData
from ..event_data import TriggerData
from ..exceptions import InvalidDefinition
from ..exceptions import TransitionNotAllowed
from ..orderedset import OrderedSet
from ..state import State
from .base import BaseEngine

if TYPE_CHECKING:
    from ..event import Event
    from ..transition import Transition

logger = logging.getLogger(__name__)


class AsyncEngine(BaseEngine):
    """Async engine with full StateChart support.

    Mirrors :class:`SyncEngine` algorithm but uses ``async``/``await`` for callback dispatch.
    All pure-computation helpers are inherited from :class:`BaseEngine`.
    """

    # --- Callback dispatch overrides (async versions of BaseEngine methods) ---

    async def _get_args_kwargs(
        self, transition: "Transition", trigger_data: TriggerData, target: "State | None" = None
    ):
        cache_key = (id(transition), id(trigger_data), id(target))

        if cache_key in self._cache:
            return self._cache[cache_key]

        event_data = EventData(trigger_data=trigger_data, transition=transition)
        if target:
            event_data.state = target
            event_data.target = target

        args, kwargs = event_data.args, event_data.extended_kwargs

        result = await self.sm._callbacks.async_call(self.sm.prepare.key, *args, **kwargs)
        for new_kwargs in result:
            kwargs.update(new_kwargs)

        self._cache[cache_key] = (args, kwargs)
        return args, kwargs

    async def _conditions_match(self, transition: "Transition", trigger_data: TriggerData):
        args, kwargs = await self._get_args_kwargs(transition, trigger_data)

        await self.sm._callbacks.async_call(
            transition.validators.key, *args, on_error=self._on_error_execution, **kwargs
        )
        return await self.sm._callbacks.async_all(
            transition.cond.key, *args, on_error=self._on_error_execution, **kwargs
        )

    async def _select_transitions(  # type: ignore[override]
        self, trigger_data: TriggerData, predicate: Callable
    ) -> "OrderedSet[Transition]":
        enabled_transitions: "OrderedSet[Transition]" = OrderedSet()

        atomic_states = (state for state in self.sm.configuration if state.is_atomic)

        async def first_transition_that_matches(
            state: State, event: "Event | None"
        ) -> "Transition | None":
            for s in chain([state], state.ancestors()):
                transition: "Transition"
                for transition in s.transitions:
                    if (
                        not transition.initial
                        and predicate(transition, event)
                        and await self._conditions_match(transition, trigger_data)
                    ):
                        return transition
            return None

        for state in atomic_states:
            transition = await first_transition_that_matches(state, trigger_data.event)
            if transition is not None:
                enabled_transitions.add(transition)

        return self._filter_conflicting_transitions(enabled_transitions)

    async def select_eventless_transitions(self, trigger_data: TriggerData):
        return await self._select_transitions(trigger_data, lambda t, _e: t.is_eventless)

    async def select_transitions(self, trigger_data: TriggerData) -> "OrderedSet[Transition]":  # type: ignore[override]
        return await self._select_transitions(trigger_data, lambda t, e: t.match(e))

    async def _execute_transition_content(
        self,
        enabled_transitions: "List[Transition]",
        trigger_data: TriggerData,
        get_key: "Callable[[Transition], str]",
        set_target_as_state: bool = False,
        **kwargs_extra,
    ):
        result = []
        for transition in enabled_transitions:
            target = transition.target if set_target_as_state else None
            args, kwargs = await self._get_args_kwargs(
                transition,
                trigger_data,
                target=target,
            )
            kwargs.update(kwargs_extra)

            result += await self.sm._callbacks.async_call(get_key(transition), *args, **kwargs)

        return result

    async def _exit_states(  # type: ignore[override]
        self, enabled_transitions: "List[Transition]", trigger_data: TriggerData
    ) -> "OrderedSet[State]":
        ordered_states, result = self._prepare_exit_states(enabled_transitions)

        for info in ordered_states:
            args, kwargs = await self._get_args_kwargs(info.transition, trigger_data)

            if info.state is not None:
                await self.sm._callbacks.async_call(
                    info.state.exit.key, *args, on_error=self._on_error_execution, **kwargs
                )

            self._remove_state_from_configuration(info.state)

        return result

    async def _enter_states(  # noqa: C901
        self,
        enabled_transitions: "List[Transition]",
        trigger_data: TriggerData,
        states_to_exit: "OrderedSet[State]",
        previous_configuration: "OrderedSet[State]",
    ):
        ordered_states, states_for_default_entry, default_history_content, new_configuration = (
            self._prepare_entry_states(enabled_transitions, states_to_exit, previous_configuration)
        )

        result = await self._execute_transition_content(
            enabled_transitions,
            trigger_data,
            lambda t: t.on.key,
            previous_configuration=previous_configuration,
            new_configuration=new_configuration,
        )

        if self.sm.atomic_configuration_update:
            self.sm.configuration = new_configuration

        for info in ordered_states:
            target = info.state
            transition = info.transition
            args, kwargs = await self._get_args_kwargs(
                transition,
                trigger_data,
                target=target,
            )

            logger.debug("Entering state: %s", target)
            self._add_state_to_configuration(target)

            on_entry_result = await self.sm._callbacks.async_call(
                target.enter.key, *args, on_error=self._on_error_execution, **kwargs
            )

            # Handle default initial states
            if target.id in {t.state.id for t in states_for_default_entry if t.state}:
                initial_transitions = [t for t in target.transitions if t.initial]
                if len(initial_transitions) == 1:
                    result += await self.sm._callbacks.async_call(
                        initial_transitions[0].on.key, *args, **kwargs
                    )

            # Handle default history states
            default_history_transitions = [
                i.transition for i in default_history_content.get(target.id, [])
            ]
            if default_history_transitions:
                await self._execute_transition_content(
                    default_history_transitions,
                    trigger_data,
                    lambda t: t.on.key,
                    previous_configuration=previous_configuration,
                    new_configuration=new_configuration,
                )

            # Handle final states
            if target.final:
                self._handle_final_state(target, on_entry_result)

        return result

    async def microstep(self, transitions: "List[Transition]", trigger_data: TriggerData):
        previous_configuration = self.sm.configuration
        try:
            result = await self._execute_transition_content(
                transitions, trigger_data, lambda t: t.before.key
            )

            states_to_exit = await self._exit_states(transitions, trigger_data)
            result += await self._enter_states(
                transitions, trigger_data, states_to_exit, previous_configuration
            )
        except InvalidDefinition:
            self.sm.configuration = previous_configuration
            raise
        except Exception as e:
            self.sm.configuration = previous_configuration
            if self.sm.error_on_execution:
                self._send_error_execution(trigger_data, e)
                return None
            raise

        try:
            await self._execute_transition_content(
                transitions,
                trigger_data,
                lambda t: t.after.key,
                set_target_as_state=True,
            )
        except InvalidDefinition:
            raise
        except Exception as e:
            if self.sm.error_on_execution:
                self._send_error_execution(trigger_data, e)
            else:
                raise

        if len(result) == 0:
            result = None
        elif len(result) == 1:
            result = result[0]

        return result

    # --- Engine loop ---

    async def _run_microstep(self, enabled_transitions, trigger_data):
        """Run a microstep for internal/eventless transitions with error handling."""
        try:
            await self.microstep(list(enabled_transitions), trigger_data)
        except InvalidDefinition:
            raise
        except Exception as e:  # pragma: no cover
            if self.sm.error_on_execution:
                self._send_error_execution(trigger_data, e)
            else:
                raise

    async def activate_initial_state(self):
        """Activate the initial state.

        In async code, the user must call this method explicitly (or it will be lazily
        activated on the first event). There's no built-in way to call async code from
        ``StateMachine.__init__``.
        """
        return await self.processing_loop()

    async def processing_loop(self):  # noqa: C901
        """Process event triggers with the 3-phase macrostep architecture.

        Phase 1: Eventless transitions + internal queue until quiescence.
        Phase 2: Remaining internal events (safety net for invoke-generated events).
        Phase 3: External events.
        """
        if not self._processing.acquire(blocking=False):
            return None

        logger.debug("Processing loop started: %s", self.sm.current_state_value)
        first_result = self._sentinel
        try:
            took_events = True
            while took_events:
                self.clear_cache()
                took_events = False
                macrostep_done = False

                # Phase 1: eventless transitions and internal events
                while not macrostep_done:
                    logger.debug("Macrostep: eventless/internal queue")

                    self.clear_cache()
                    internal_event = TriggerData(self.sm, event=None)  # null object for eventless
                    enabled_transitions = await self.select_eventless_transitions(internal_event)
                    if not enabled_transitions:
                        if self.internal_queue.is_empty():
                            macrostep_done = True
                        else:
                            internal_event = self.internal_queue.pop()
                            enabled_transitions = await self.select_transitions(internal_event)
                    if enabled_transitions:
                        logger.debug("Enabled transitions: %s", enabled_transitions)
                        took_events = True
                        await self._run_microstep(enabled_transitions, internal_event)

                # Phase 2: remaining internal events
                while not self.internal_queue.is_empty():  # pragma: no cover
                    internal_event = self.internal_queue.pop()
                    enabled_transitions = await self.select_transitions(internal_event)
                    if enabled_transitions:
                        await self._run_microstep(enabled_transitions, internal_event)

                # Phase 3: external events
                logger.debug("Macrostep: external queue")
                while not self.external_queue.is_empty():
                    self.clear_cache()
                    took_events = True
                    external_event = self.external_queue.pop()
                    current_time = time()
                    if external_event.execution_time > current_time:
                        self.put(external_event, _delayed=True)
                        await asyncio.sleep(self.sm._loop_sleep_in_ms)
                        continue

                    logger.debug("External event: %s", external_event.event)

                    # Handle lazy initial state activation.
                    # Break out of phase 3 so the outer loop restarts from phase 1
                    # (eventless/internal), ensuring internal events queued during
                    # initial entry are processed before any external events.
                    if external_event.event == "__initial__":
                        transitions = self._initial_transitions(external_event)
                        await self._enter_states(
                            transitions, external_event, OrderedSet(), OrderedSet()
                        )
                        break

                    enabled_transitions = await self.select_transitions(external_event)
                    logger.debug("Enabled transitions: %s", enabled_transitions)
                    if enabled_transitions:
                        try:
                            result = await self.microstep(
                                list(enabled_transitions), external_event
                            )
                            if first_result is self._sentinel:
                                first_result = result
                        except Exception:
                            self.clear()
                            raise

                    else:
                        if not self.sm.allow_event_without_transition:
                            raise TransitionNotAllowed(external_event.event, self.sm.configuration)

        finally:
            self._processing.release()
        return first_result if first_result is not self._sentinel else None
