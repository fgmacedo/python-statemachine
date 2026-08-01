import asyncio
import contextvars
from collections.abc import Callable
from itertools import chain
from time import time
from typing import TYPE_CHECKING

from ..event_data import EventData
from ..event_data import TriggerData
from ..exceptions import InvalidDefinition
from ..exceptions import TransitionNotAllowed
from ..orderedset import OrderedSet
from ..state import State
from .base import _ERROR_EXECUTION
from .base import BaseEngine

if TYPE_CHECKING:
    from ..transition import Transition

# ContextVar to distinguish reentrant calls (from within callbacks) from
# concurrent external calls. asyncio propagates context to child tasks
# (e.g., those created by asyncio.gather in the callback system), so a
# ContextVar set in the processing loop is visible in all callbacks.
# Independent external coroutines have their own context where this is False.
_in_processing_loop: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_in_processing_loop", default=False
)


class AsyncEngine(BaseEngine):
    """Async engine with full StateChart support.

    Mirrors :class:`SyncEngine` algorithm but uses ``async``/``await`` for callback dispatch.
    All pure-computation helpers are inherited from :class:`BaseEngine`.
    """

    def put(self, trigger_data: TriggerData, internal: bool = False, _delayed: bool = False):
        """Override to attach an asyncio.Future for external events.

        Futures are only created when:
        - The event is external (not internal)
        - No future is already attached
        - There is a running asyncio loop
        - The call is NOT from within the processing loop (reentrant calls
          from callbacks must not get futures, as that would deadlock)
        """
        if not internal and trigger_data.future is None and not _in_processing_loop.get():
            try:
                loop = asyncio.get_running_loop()
                trigger_data.future = loop.create_future()
            except RuntimeError:
                pass  # No running loop — sync caller
        super().put(trigger_data, internal=internal, _delayed=_delayed)

    @staticmethod
    def _resolve_future(future: "asyncio.Future[object] | None", result):
        """Resolve a future with the given result, if present and not yet done."""
        if future is not None and not future.done():
            future.set_result(result)

    @staticmethod
    def _reject_future(future: "asyncio.Future[object] | None", exc: Exception):
        """Reject a future with the given exception, if present and not yet done."""
        if future is not None and not future.done():
            future.set_exception(exc)

    def _reject_pending_futures(self, exc: Exception):
        """Reject all unresolved futures in the external queue."""
        self.external_queue.reject_futures(exc)

    # --- Callback dispatch overrides (async versions of BaseEngine methods) ---

    async def _get_args_kwargs(
        self,
        transition: "Transition",
        trigger_data: TriggerData,
        target: "State | None" = None,
        source: "State | None" = None,
    ):
        cache_key = (id(transition), id(trigger_data), id(target), id(source))

        if cache_key in self._cache:
            return self._cache[cache_key]

        event_data = EventData(trigger_data=trigger_data, transition=transition)
        # See the sync engine for the rationale: bind `state`/`target` to the
        # entered state and `state`/`source` to the exited state, keeping the
        # generic enter/exit callbacks symmetric across compound boundaries.
        if target:
            event_data.state = target
            event_data.target = target
        if source:
            event_data.state = source
            event_data.source = source

        args, kwargs = event_data.args, event_data.extended_kwargs

        result = await self.sm._callbacks.async_call(self.sm.prepare.key, *args, **kwargs)
        for new_kwargs in result:
            kwargs.update(new_kwargs)

        self._cache[cache_key] = (args, kwargs)
        return args, kwargs

    async def _conditions_match(self, transition: "Transition", trigger_data: TriggerData):
        args, kwargs = await self._get_args_kwargs(transition, trigger_data)
        on_error = self._on_error_handler()

        await self.sm._callbacks.async_call(
            transition.validators.key, *args, on_error=None, **kwargs
        )
        return await self.sm._callbacks.async_all(
            transition.cond.key, *args, on_error=on_error, **kwargs
        )

    async def _first_transition_that_matches(  # type: ignore[override]
        self,
        state: State,
        trigger_data: TriggerData,
        predicate: Callable,
    ) -> "Transition | None":
        for s in chain([state], state.ancestors()):
            transition: "Transition"
            for transition in s.transitions:
                if (
                    not transition.initial
                    and predicate(transition, trigger_data.event)
                    and await self._conditions_match(transition, trigger_data)
                ):
                    return transition
        return None

    async def _select_transitions(  # type: ignore[override]
        self, trigger_data: TriggerData, predicate: Callable
    ) -> "OrderedSet[Transition]":
        enabled_transitions: "OrderedSet[Transition]" = OrderedSet()

        atomic_states = (state for state in self.sm.configuration if state.is_atomic)

        for state in atomic_states:
            transition = await self._first_transition_that_matches(state, trigger_data, predicate)
            if transition is not None:
                enabled_transitions.add(transition)

        return self._filter_conflicting_transitions(enabled_transitions)

    async def select_eventless_transitions(self, trigger_data: TriggerData):
        return await self._select_transitions(trigger_data, lambda t, _e: t.is_eventless)

    async def select_transitions(self, trigger_data: TriggerData) -> "OrderedSet[Transition]":  # type: ignore[override]
        return await self._select_transitions(trigger_data, lambda t, e: t.match(e))

    async def _execute_transition_content(
        self,
        enabled_transitions: "list[Transition]",
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
        self, enabled_transitions: "list[Transition]", trigger_data: TriggerData
    ) -> "OrderedSet[State]":
        ordered_states, result = self._prepare_exit_states(enabled_transitions)
        on_error = self._on_error_handler()

        for info in ordered_states:
            # Cancel invocations for this state before executing exit handlers.
            if info.state is not None:  # pragma: no branch
                self._invoke_manager.cancel_for_state(info.state)

            args, kwargs = await self._get_args_kwargs(
                info.transition, trigger_data, source=info.state
            )

            if info.state is not None:  # pragma: no branch
                self._debug("%s Exiting state: %s", self._log_id, info.state)
                await self.sm._callbacks.async_call(
                    info.state.exit.key, *args, on_error=on_error, **kwargs
                )

            self._remove_state_from_configuration(info.state)

        return result

    async def _enter_states(  # noqa: C901
        self,
        enabled_transitions: "list[Transition]",
        trigger_data: TriggerData,
        states_to_exit: "OrderedSet[State]",
        previous_configuration: "OrderedSet[State]",
    ):
        on_error = self._on_error_handler()
        ordered_states, states_for_default_entry, default_history_content, new_configuration = (
            self._prepare_entry_states(enabled_transitions, states_to_exit, previous_configuration)
        )

        # For transition 'on' content, use on_error only for non-error.execution
        # events.  During error.execution processing, errors in transition content
        # must propagate to microstep() where _send_error_execution's guard
        # prevents infinite loops (per SCXML spec: errors during error event
        # processing are ignored).
        on_error_transition = on_error
        if (
            on_error is not None
            and trigger_data.event
            and str(trigger_data.event) == _ERROR_EXECUTION
        ):
            on_error_transition = None

        result = await self._execute_transition_content(
            enabled_transitions,
            trigger_data,
            lambda t: t.on.key,
            on_error=on_error_transition,
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

            self._debug("%s Entering state: %s", self._log_id, target)
            self._add_state_to_configuration(target)

            on_entry_result = await self.sm._callbacks.async_call(
                target.enter.key, *args, on_error=on_error, **kwargs
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

            # Mark state for invocation if it has invoke callbacks registered
            if target.invoke.key in self.sm._callbacks:
                self._invoke_manager.mark_for_invoke(target, trigger_data.kwargs)

            # Handle final states
            if target.final:
                self._handle_final_state(target, on_entry_result)

        return result

    async def microstep(self, transitions: "list[Transition]", trigger_data: TriggerData):
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
            self._handle_error(e, trigger_data)
            return None

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
            self._handle_error(e, trigger_data)

        if len(result) == 0:
            result = None
        elif len(result) == 1:
            result = result[0]

        return result

    # --- Engine loop ---

    async def _run_microstep(self, enabled_transitions, trigger_data):  # pragma: no cover
        """Run a microstep for internal/eventless transitions with error handling.

        Note: microstep() handles its own errors internally, so this try/except
        is a safety net that is not expected to be reached in normal operation.
        """
        try:
            await self.microstep(list(enabled_transitions), trigger_data)
        except InvalidDefinition:
            raise
        except Exception as e:
            self._handle_error(e, trigger_data)

    async def activate_initial_state(self, **kwargs):
        """Activate the initial state.

        In async code, the user must call this method explicitly (or it will be lazily
        activated on the first event). There's no built-in way to call async code from
        ``StateMachine.__init__``.

        Any ``**kwargs`` are forwarded to initial state entry callbacks via dependency
        injection, just like event kwargs on ``send()``.
        """
        return await self.processing_loop()

    async def processing_loop(  # noqa: C901
        self, caller_future: "asyncio.Future[object] | None" = None
    ):
        """Process event triggers with the 3-phase macrostep architecture.

        Phase 1: Eventless transitions + internal queue until quiescence.
        Phase 2: Remaining internal events (safety net for invoke-generated events).
        Phase 3: External events.

        When ``caller_future`` is provided, the caller can ``await`` it to
        receive its own event's result — even if another coroutine holds the
        processing lock.
        """
        if not self._processing.acquire(blocking=False):
            # Another coroutine holds the lock and will process our event.
            # Await the caller's future so we get our own result back.
            if caller_future is not None:
                return await caller_future
            return None

        _ctx_token = _in_processing_loop.set(True)
        self._debug("%s Processing loop started: %s", self._log_id, self.sm.current_state_value)
        first_result = self._sentinel
        try:
            took_events = True
            while took_events and self.running:
                self.clear_cache()
                took_events = False
                macrostep_done = False

                # Phase 1: eventless transitions and internal events
                while not macrostep_done:
                    self._microstep_count = 0
                    self._debug(
                        "%s Macrostep %d: eventless/internal queue",
                        self._log_id,
                        self._macrostep_count,
                    )

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
                        self._debug(
                            "%s Enabled transitions: %s", self._log_id, enabled_transitions
                        )
                        took_events = True
                        await self._run_microstep(enabled_transitions, internal_event)

                # Spawn invoke handlers for states entered during this macrostep.
                await self._invoke_manager.spawn_pending_async()
                self._check_root_final_state()

                # Phase 2: remaining internal events
                while not self.internal_queue.is_empty():  # pragma: no cover
                    internal_event = self.internal_queue.pop()
                    enabled_transitions = await self.select_transitions(internal_event)
                    if enabled_transitions:
                        await self._run_microstep(enabled_transitions, internal_event)

                # Phase 3: external events
                self._debug("%s Macrostep %d: external queue", self._log_id, self._macrostep_count)
                while not self.external_queue.is_empty():
                    self.clear_cache()
                    took_events = True
                    external_event = self.external_queue.pop()
                    current_time = time()
                    if external_event.execution_time > current_time:
                        self.put(external_event, _delayed=True)
                        await asyncio.sleep(self.sm._loop_sleep_in_ms)
                        # Break to Phase 1 so internal events and eventless
                        # transitions can be processed while we wait.
                        break

                    self._macrostep_count += 1
                    self._microstep_count = 0
                    self._debug(
                        "%s macrostep %d: event=%s",
                        self._log_id,
                        self._macrostep_count,
                        external_event.event,
                    )

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

                    # Finalize + autoforward for active invocations
                    self._invoke_manager.handle_external_event(external_event)

                    event_future = external_event.future
                    try:
                        enabled_transitions = await self.select_transitions(external_event)
                        self._debug(
                            "%s Enabled transitions: %s", self._log_id, enabled_transitions
                        )
                        if enabled_transitions:
                            result = await self.microstep(
                                list(enabled_transitions), external_event
                            )
                            self._resolve_future(event_future, result)
                            if first_result is self._sentinel:
                                first_result = result
                        else:
                            if not self.sm.allow_event_without_transition:
                                tna = TransitionNotAllowed(
                                    external_event.event, self.sm.configuration
                                )
                                self._reject_future(event_future, tna)
                                self._reject_pending_futures(tna)
                                raise tna
                            # Event allowed but no transition — resolve with None
                            self._resolve_future(event_future, None)
                    except Exception as exc:
                        self._reject_future(event_future, exc)
                        self._reject_pending_futures(exc)
                        self.clear()
                        raise

        except Exception as exc:
            if caller_future is not None:
                # Route the exception to the caller's future if still pending.
                # If already resolved (caller's own event succeeded before a
                # later event failed), suppress the exception — the caller will
                # get their successful result via ``await future`` below, and
                # the failing event's exception was already routed to *its*
                # caller's future by ``_reject_future(event_future, ...)``.
                self._reject_future(caller_future, exc)
            else:
                raise
        finally:
            _in_processing_loop.reset(_ctx_token)
            self._processing.release()

        self._debug("%s Processing loop ended", self._log_id)
        result = first_result if first_result is not self._sentinel else None
        # If the caller has a future, await it (already resolved by now).
        if caller_future is not None:
            # Resolve the future if it wasn't processed (e.g. machine terminated).
            self._resolve_future(caller_future, result)
            return await caller_future
        return result

    async def enabled_events(self, *args, **kwargs):
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
                        if await sm._callbacks.async_all(
                            transition.cond.key, *args, **extended_kwargs
                        ):
                            enabled[event] = getattr(sm, event)
                    except Exception:
                        enabled[event] = getattr(sm, event)
        return list(enabled.values())
