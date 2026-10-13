import asyncio
from collections.abc import Callable
from itertools import chain
from time import monotonic
from typing import TYPE_CHECKING

from ..event_data import EventData
from ..event_data import TriggerData
from ..exceptions import InvalidDefinition
from ..exceptions import StateMachineError
from ..exceptions import TransitionNotAllowed
from ..i18n import _
from ..orderedset import OrderedSet
from ..state import State
from .base import _ERROR_EXECUTION
from .base import BaseEngine
from .base import _processing_step
from .base import _running_engine

if TYPE_CHECKING:
    from ..statemachine import StateChart
    from ..transition import Transition


class _MacrostepCaller:
    """The caller of the external event whose macrostep is running, answered once the
    macrostep ends, so that an exception raised by its internal events or eventless
    transitions still reaches it."""

    def __init__(self):
        self.future: "asyncio.Future[object] | None" = None
        self.result: object = None

    def answer(self):
        AsyncEngine._resolve_future(self.future, self.result)
        self.future = None
        self.result = None

    def reject(self, exc: Exception) -> bool:
        """Reject the caller with ``exc``; returns whether a caller was still waiting."""
        if self.future is None or self.future.done():
            return False
        self.future.set_exception(exc)
        return True

    def interrupt(self):
        self.reject(
            StateMachineError(
                _(
                    "The task running the processing loop was cancelled while it processed "
                    "this event."
                )
            )
        )


class AsyncEngine(BaseEngine):
    """Async engine with full StateChart support.

    Mirrors :class:`SyncEngine` algorithm but uses ``async``/``await`` for callback dispatch.
    All pure-computation helpers are inherited from :class:`BaseEngine`.
    """

    def __init__(self, sm: "StateChart"):
        super().__init__(sm)
        self._lock_waiters: "set[asyncio.Future[object]]" = set()

    def put(self, trigger_data: TriggerData, internal: bool = False):
        """Override to attach an asyncio.Future to a trigger put from outside the loop.

        Such a trigger always lands on the external queue, and its caller awaits the future
        for its result. Futures are only created when:
        - No future is already attached
        - There is a running asyncio loop
        - The call is NOT from within the processing loop (reentrant calls
          from callbacks must not get futures, as that would deadlock)
        """
        if trigger_data.future is None and _running_engine.get() is None:
            try:
                loop = asyncio.get_running_loop()
                trigger_data.future = loop.create_future()
            except RuntimeError:
                pass  # No running loop — sync caller
        super().put(trigger_data, internal=internal)

    @staticmethod
    def _resolve_future(future: "asyncio.Future[object] | None", result):
        """Resolve a future with the given result, if present and not yet done."""
        if future is not None and not future.done():
            future.set_result(result)

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

    async def _first_transition_that_matches(
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

    async def _select_transitions(
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

    async def select_transitions(self, trigger_data: TriggerData) -> "OrderedSet[Transition]":
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

    async def _exit_states(
        self, enabled_transitions: "list[Transition]", trigger_data: TriggerData
    ) -> "OrderedSet[State]":
        ordered_states, result = self._prepare_exit_states(enabled_transitions)
        on_error = self._on_error_handler()

        for info in ordered_states:
            # Cancel invocations for this state before executing exit handlers.
            self._invoke_manager.cancel_for_state(info.state)

            args, kwargs = await self._get_args_kwargs(
                info.transition, trigger_data, source=info.state
            )

            self._debug("%s Exiting state: %s", self._log_id, info.state)
            await self.sm._callbacks.async_call(
                info.state.exit.key, *args, on_error=on_error, **kwargs
            )

            self._remove_state_from_configuration(info.state)

        return result

    async def _enter_states(
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

    async def activate_initial_state(self, **kwargs):
        """Activate the initial state.

        In async code, the user must call this method explicitly (or it will be lazily
        activated on the first event). There's no built-in way to call async code from
        ``StateMachine.__init__``.

        Any ``**kwargs`` are forwarded to initial state entry callbacks via dependency
        injection, just like event kwargs on ``send()``.
        """
        return await self.processing_loop()

    async def processing_loop(self, caller_future: "asyncio.Future[object] | None" = None):
        """Process event triggers, a macrostep at a time.

        Each macrostep takes eventless transitions and internal events until neither enables a
        transition, spawns the invocations of the states it entered, and then takes the
        external events that are due.

        When ``caller_future`` is provided, the caller can ``await`` it to
        receive its own event's result — even if another coroutine holds the
        processing lock. If that coroutine is cancelled, the caller takes the loop over.
        """
        while not self._processing.acquire(blocking=False):
            if caller_future is None:
                return None
            await self._wait_for_result_or_release(caller_future)
            if caller_future.done():
                return caller_future.result()

        try:
            return await self._run_processing_loop(caller_future)
        finally:
            self._processing.release()
            self._wake_lock_waiters()

    async def _wait_for_result_or_release(self, caller_future: "asyncio.Future[object]"):
        """Wait until the caller's event is answered or the processing lock is released.

        A caller cancelled here cancels its future, so its event, still processed, answers
        nobody.
        """
        released = caller_future.get_loop().create_future()
        self._lock_waiters.add(released)
        try:
            await asyncio.wait((caller_future, released), return_when=asyncio.FIRST_COMPLETED)
        except BaseException:
            caller_future.cancel()
            raise
        finally:
            self._lock_waiters.discard(released)

    def _wake_lock_waiters(self):
        for released in self._lock_waiters:
            self._resolve_future(released, None)

    async def _run_processing_loop(self, caller_future: "asyncio.Future[object] | None"):
        self._debug("%s Processing loop started: %s", self._log_id, self.sm.current_state_value)
        first_result = self._sentinel
        macrostep = _MacrostepCaller()
        try:
            with _processing_step(self):
                took_events = True
                while took_events and self.running:
                    self.clear_cache()
                    took_events = await self._run_macrostep()

                    # Spawn invoke handlers for states entered during this macrostep.
                    await self._invoke_manager.spawn_pending_async()
                    macrostep.answer()
                    self._check_root_final_state()
                    if not self.running:
                        break

                    took_external_events, first_result = await self._take_due_external_event(
                        first_result, macrostep
                    )
                    took_events = took_events or took_external_events

                macrostep.answer()
                if not self.running:
                    self._drop_external_events()

        except Exception as exc:
            answered = caller_future is None or caller_future.done()
            self._reject_pending_futures(exc)
            self.clear()
            if not macrostep.reject(exc) and answered:
                raise
        except BaseException:
            self.internal_queue.clear()
            macrostep.interrupt()
            if caller_future is not None:
                caller_future.cancel()
            raise

        self._debug("%s Processing loop ended", self._log_id)
        result = first_result if first_result is not self._sentinel else None
        if caller_future is not None:
            # Resolve the future if it wasn't processed (e.g. machine terminated).
            self._resolve_future(caller_future, result)
            return await caller_future
        return result

    async def _run_macrostep(self) -> bool:
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
            internal_event = TriggerData(self.sm, event=None)  # null object for eventless
            enabled_transitions = await self.select_eventless_transitions(internal_event)
            if not enabled_transitions:
                if self.internal_queue.is_empty():
                    return took_events
                internal_event = self.internal_queue.pop()
                enabled_transitions = await self.select_transitions(internal_event)
            if enabled_transitions:
                self._debug("%s Enabled transitions: %s", self._log_id, enabled_transitions)
                took_events = True
                await self.microstep(list(enabled_transitions), internal_event)

    async def _take_due_external_event(self, first_result, macrostep: "_MacrostepCaller"):
        """Take the external event at the head of the queue, if it is due.

        One at a time, so the macrostep that follows runs the internal events and eventless
        transitions it enabled before the next external event is taken. The event's caller is
        left in ``macrostep``, to be answered once that macrostep ends.

        Returns whether the queue held an event, and ``first_result`` updated with the result
        of the first event that enabled a transition.
        """
        self._debug("%s Macrostep %d: external queue", self._log_id, self._macrostep_count)
        if self.external_queue.is_empty():
            return False, first_result

        self.clear_cache()
        external_event = self.external_queue.pop_due(monotonic())
        if external_event is None:
            await asyncio.sleep(self.sm._loop_sleep_in_ms)
            return True, first_result

        self._macrostep_count += 1
        self._microstep_count = 0
        self._debug(
            "%s macrostep %d: event=%s",
            self._log_id,
            self._macrostep_count,
            external_event.event,
        )

        # Handle lazy initial state activation.
        if external_event.event == "__initial__":
            transitions = self._initial_transitions(external_event)
            await self._enter_states(transitions, external_event, OrderedSet(), OrderedSet())
            return True, first_result

        macrostep.future = external_event.future
        result = await self._take_external_event(external_event)
        if result is not self._sentinel:
            macrostep.result = result
        if first_result is self._sentinel:
            first_result = result
        return True, first_result

    async def _take_external_event(self, external_event: TriggerData):
        """Run one external event.

        Returns the event's microstep result, or the sentinel when it enabled no transition.
        """
        # Finalize + autoforward for active invocations
        self._invoke_manager.handle_external_event(external_event)

        enabled_transitions = await self.select_transitions(external_event)
        self._debug("%s Enabled transitions: %s", self._log_id, enabled_transitions)
        if enabled_transitions:
            return await self.microstep(list(enabled_transitions), external_event)
        if not self.sm.allow_event_without_transition:
            raise TransitionNotAllowed(external_event.event, self.sm.configuration)
        return self._sentinel

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
