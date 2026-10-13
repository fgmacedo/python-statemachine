import logging
from collections.abc import Callable
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from dataclasses import field
from heapq import heappop
from queue import PriorityQueue
from queue import Queue
from threading import Lock
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from ..event import BoundEvent
from ..event_data import EventData
from ..event_data import TriggerData
from ..exceptions import InvalidDefinition
from ..exceptions import TransitionNotAllowed
from ..invoke import InvokeManager
from ..orderedset import OrderedSet
from ..state import HistoryState
from ..state import State
from ..transition import Transition

if TYPE_CHECKING:
    from ..statemachine import StateChart

logger = logging.getLogger(__name__)

_running_engine: "ContextVar[BaseEngine | None]" = ContextVar("_running_engine", default=None)
"""The engine whose step the current thread or task is running, if any.

A context variable is per thread and per asyncio task: asyncio copies it into the tasks a
step creates, so callbacks see it, while another thread or an independent coroutine sending
to the same machine does not.
"""


@contextmanager
def _processing_step(engine: "BaseEngine") -> Iterator[None]:
    """Mark the current context as running a step of ``engine``, until the block ends."""
    token = _running_engine.set(engine)
    try:
        yield
    finally:
        _running_engine.reset(token)


@dataclass(frozen=True, unsafe_hash=True, eq=True)
class StateTransition:
    transition: Transition = field(compare=False)
    state: State


#: What entering states needs, worked out before any callback runs: the states in entry order,
#: those entered by default, the default history content, and the new configuration.
_EntryPlan = tuple[
    list[StateTransition], OrderedSet[StateTransition], dict[str, Any], OrderedSet[State]
]


class EventQueue:
    def __init__(self):
        self.queue: Queue = PriorityQueue()

    def __repr__(self):
        return f"EventQueue({self.queue.queue!r}, size={self.queue.qsize()})"

    def is_empty(self):
        """Whether the queue holds no trigger that has not been cancelled."""
        with self.queue.mutex:
            self._drop_cancelled_head()
            return not self.queue.queue

    def _drop_cancelled_head(self):
        """Drop the cancelled triggers at the head. The caller holds the queue's mutex."""
        heap = self.queue.queue
        while heap and heap[0].cancelled:
            heappop(heap)

    def put(self, trigger_data: TriggerData):
        """Put the trigger on the queue without blocking the caller."""
        self.queue.put(trigger_data)

    def pop(self):
        """Pop a trigger from the queue without blocking the caller."""
        return self.queue.get(block=False)

    def pop_due(self, now: float) -> "TriggerData | None":
        """Pop the trigger at the head if it is due by ``now``.

        Returns ``None`` when the queue is empty or its head is not yet due. The head stays in
        the queue until it is popped, so a :meth:`cancel` from another thread always finds it.
        """
        with self.queue.mutex:
            self._drop_cancelled_head()
            heap: list[TriggerData] = self.queue.queue
            if not heap or heap[0].execution_time > now:
                return None
            return heappop(heap)

    def clear(self):
        with self.queue.mutex:
            self.queue.queue.clear()

    def drain(self) -> list[TriggerData]:
        """Remove every trigger from the queue and return those not cancelled."""
        with self.queue.mutex:
            triggers = [trigger for trigger in self.queue.queue if not trigger.cancelled]
            self.queue.queue.clear()
        return triggers

    def reject_futures(self, exc: Exception):
        """Reject all unresolved futures in the queue.

        Called when the processing loop exits abnormally so that coroutines
        awaiting their futures don't hang forever.
        """
        with self.queue.mutex:
            for trigger_data in self.queue.queue:
                future = trigger_data.future
                if future is not None and not future.done():
                    future.set_exception(exc)

    def cancel(self, send_id: str):
        """Cancel every trigger with this ``send_id``, and answer a caller awaiting one with
        ``None``. Each stays where it is, so the heap keeps its order, until :meth:`is_empty`
        drops it from the head."""
        with self.queue.mutex:
            for trigger_data in self.queue.queue:
                if trigger_data.send_id == send_id:
                    trigger_data.cancelled = True
                    future = trigger_data.future
                    if future is not None and not future.done():
                        future.set_result(None)


_ERROR_EXECUTION = "error.execution"


class BaseEngine:
    def __init__(self, sm: "StateChart"):
        self.sm: "StateChart" = sm
        self.external_queue = EventQueue()
        self.internal_queue = EventQueue()
        self._sentinel = object()
        self.running = True
        self._processing = Lock()
        self._cache: dict = {}  # Cache for _get_args_kwargs results
        self._invoke_manager = InvokeManager(self)
        self._macrostep_count: int = 0
        self._microstep_count: int = 0
        self._log_id = f"[{type(sm).__name__}]"
        self._debug = logger.debug if logger.isEnabledFor(logging.DEBUG) else lambda *a, **k: None
        self._root_parallel_final_pending: "State | None" = None

    def clear_cache(self):
        """Clears the cache. Should be called at the start of each processing loop."""
        self._cache.clear()

    def put(self, trigger_data: TriggerData, internal: bool = False):
        """Put the trigger on the queue without blocking the caller.

        An ``internal`` trigger joins the internal queue only when this machine raises it while
        running a step. Put from outside, including from a step of another machine, there is
        no macrostep to join, so it goes to the external queue, where its caller gets its
        result.
        """
        if not self.running and not self.sm.allow_event_without_transition:
            raise TransitionNotAllowed(trigger_data.event, self.sm.configuration)

        internal = internal and _running_engine.get() is self
        if internal:
            self.internal_queue.put(trigger_data)
        else:
            self.external_queue.put(trigger_data)

        self._debug(
            "%s New event '%s' put on the '%s' queue",
            self._log_id,
            trigger_data.event,
            "internal" if internal else "external",
        )

    def clear(self):
        self.internal_queue.clear()
        self.external_queue.clear()

    def _drop_external_events(self):
        """Drop the external events left once the machine has stopped, answering a caller
        awaiting one as the stopped machine answers a new event."""
        for trigger_data in self.external_queue.drain():
            future = trigger_data.future
            if future is None or future.done():
                continue
            if self.sm.allow_event_without_transition:
                future.set_result(None)
            else:
                future.set_exception(
                    TransitionNotAllowed(trigger_data.event, self.sm.configuration)
                )

    def cancel_event(self, send_id: str):
        """Cancel the event with the given send_id."""
        self.external_queue.cancel(send_id)

    def _on_error_handler(self) -> "Callable[[Exception], None] | None":
        """Return a per-block error handler, or ``None``.

        When ``catch_errors_as_events`` is enabled, returns a callable that queues
        ``error.execution`` on the internal queue.  Otherwise returns ``None``
        so that exceptions propagate normally.
        """
        if not self.sm.catch_errors_as_events:
            return None

        def handler(error: Exception) -> None:
            if isinstance(error, InvalidDefinition):
                raise error
            # Per-block errors always queue error.execution — even when the current
            # event is itself error.execution.  The SCXML spec mandates that the
            # new error.execution is a separate event that may trigger a different
            # transition (see W3C test 152).  The infinite-loop guard lives at the
            # *microstep* level (in ``_send_error_execution``), not here.
            BoundEvent(_ERROR_EXECUTION, internal=True, _sm=self.sm).put(error=error)

        return handler

    def _handle_error(self, error: Exception, trigger_data: TriggerData):
        """Handle an execution error: send ``error.execution`` or re-raise.

        Centralises the ``if catch_errors_as_events`` check so callers don't need
        to know about the variation.
        """
        if self.sm.catch_errors_as_events:
            self._send_error_execution(error, trigger_data)
        else:
            raise error

    def _send_error_execution(self, error: Exception, trigger_data: TriggerData):
        """Send error.execution to internal queue (SCXML spec).

        If already processing an error.execution event, ignore to avoid infinite loops.
        """
        self._debug(
            "%s Error %s captured while executing event=%s",
            self._log_id,
            error,
            trigger_data.event,
        )
        if trigger_data.event and str(trigger_data.event) == _ERROR_EXECUTION:
            logger.warning("Error while processing error.execution, ignoring: %s", error)
            return
        BoundEvent(_ERROR_EXECUTION, internal=True, _sm=self.sm).put(error=error)

    def start(self, **kwargs):
        if self.sm.current_state_value is not None:
            return

        BoundEvent("__initial__", _sm=self.sm).put(**kwargs)

    def _initial_transitions(self, trigger_data):
        empty_state = State()
        configuration = self.sm._get_initial_configuration()
        transitions = [
            Transition(empty_state, state, event="__initial__") for state in configuration
        ]
        for transition in transitions:
            transition._specs.clear()
        return transitions

    def _filter_conflicting_transitions(
        self, transitions: OrderedSet[Transition]
    ) -> OrderedSet[Transition]:
        """
        Remove transições conflitantes, priorizando aquelas com estados de origem descendentes
        ou que aparecem antes na ordem do documento.

        Args:
            transitions (OrderedSet[Transition]): Conjunto de transições habilitadas.

        Returns:
            OrderedSet[Transition]: Conjunto de transições sem conflitos.
        """
        filtered_transitions = OrderedSet[Transition]()

        # Ordena as transições na ordem dos estados que as selecionaram
        for t1 in transitions:
            t1_preempted = False
            transitions_to_remove = OrderedSet[Transition]()

            # Verifica conflitos com as transições já filtradas
            for t2 in filtered_transitions:
                # Calcula os conjuntos de saída (exit sets)
                t1_exit_set = self._compute_exit_set([t1])
                t2_exit_set = self._compute_exit_set([t2])

                # Verifica interseção dos conjuntos de saída
                if t1_exit_set & t2_exit_set:  # Há interseção
                    if t1.source.is_descendant(t2.source):
                        # t1 é preferido pois é descendente de t2
                        transitions_to_remove.add(t2)
                    else:
                        # t2 é preferido pois foi selecionado antes na ordem do documento
                        t1_preempted = True
                        break

            # Se t1 não foi preemptado, adiciona a lista filtrada e remove os conflitantes
            if not t1_preempted:
                for t3 in transitions_to_remove:
                    filtered_transitions.discard(t3)
                filtered_transitions.add(t1)

        return filtered_transitions

    def _compute_exit_set(self, transitions: list[Transition]) -> OrderedSet[StateTransition]:
        """Compute the exit set for a transition."""

        states_to_exit = OrderedSet[StateTransition]()

        for transition in transitions:
            if not transition.targets:
                continue
            domain = self.get_transition_domain(transition)
            for state in self.sm.configuration:
                if domain is None or state.is_descendant(domain):
                    info = StateTransition(transition=transition, state=state)
                    states_to_exit.add(info)

        return states_to_exit

    def get_transition_domain(self, transition: Transition) -> "State | None":
        """
        Return the compound state such that
        1) all states that are exited or entered as a result of taking 'transition' are
           descendants of it
        2) no descendant of it has this property.
        """
        states = self.get_effective_target_states(transition)
        if not states:
            return None
        elif (
            transition.internal
            and transition.source.is_compound
            and all(state.is_descendant(transition.source) for state in states)
        ):
            return transition.source
        elif (
            transition.internal
            and transition.is_self
            and transition.target
            and transition.target.is_atomic
        ):
            return transition.source
        else:
            return self.find_lcca([transition.source] + list(states))

    @staticmethod
    def find_lcca(states: list[State]) -> "State | None":
        """
        Find the Least Common Compound Ancestor (LCCA) of the given list of states.

        Args:
            state_list: A list of states.

        Returns:
            The LCCA state, which is a proper ancestor of all states in the list,
            or None if no such ancestor exists.
        """
        # Get ancestors of the first state in the list, filtering for compound or SCXML elements
        head, *tail = states
        ancestors = [anc for anc in head.ancestors() if anc.is_compound]

        # Find the first ancestor that is also an ancestor of all other states in the list
        ancestor: State
        for ancestor in ancestors:
            if all(state.is_descendant(ancestor) for state in tail):
                return ancestor

        return None

    def get_effective_target_states(self, transition: Transition) -> OrderedSet[State]:
        targets = OrderedSet[State]()
        for state in transition.targets:
            if state.is_history:
                if state.id in self.sm.history_values:
                    targets.update(self.sm.history_values[state.id])
                else:
                    targets.update(
                        state
                        for t in state.transitions
                        for state in self.get_effective_target_states(t)
                    )
            else:
                targets.add(state)

        return targets

    def _get_args_kwargs(
        self,
        transition: Transition,
        trigger_data: TriggerData,
        target: "State | None" = None,
        source: "State | None" = None,
    ):
        # Generate a unique key for the cache, the cache is invalidated once per loop
        cache_key = (id(transition), id(trigger_data), id(target), id(source))

        # Check the cache for existing results
        if cache_key in self._cache:
            return self._cache[cache_key]

        event_data = EventData(trigger_data=trigger_data, transition=transition)
        # Bind `state`/`target` to the individual state being entered, and
        # `state`/`source` to the individual state being exited, so the generic
        # `on_enter_state`/`on_exit_state` callbacks stay symmetric when crossing
        # compound state boundaries (the transition only knows its own endpoints).
        if target:
            event_data.state = target
            event_data.target = target
        if source:
            event_data.state = source
            event_data.source = source

        args, kwargs = event_data.args, event_data.extended_kwargs

        result = self.sm._callbacks.call(self.sm.prepare.key, *args, **kwargs)
        for new_kwargs in result:
            kwargs.update(new_kwargs)

        # Store the result in the cache
        self._cache[cache_key] = (args, kwargs)
        return args, kwargs

    def _conditions_match(self, transition: Transition, trigger_data: TriggerData):
        args, kwargs = self._get_args_kwargs(transition, trigger_data)
        on_error = self._on_error_handler()

        self.sm._callbacks.call(transition.validators.key, *args, on_error=None, **kwargs)
        return self.sm._callbacks.all(transition.cond.key, *args, on_error=on_error, **kwargs)

    def _prepare_exit_states(
        self,
        enabled_transitions: list[Transition],
    ) -> "tuple[list[StateTransition], OrderedSet[State]]":
        """Compute exit set, sort, and update history. Pure computation, no callbacks."""
        states_to_exit = self._compute_exit_set(enabled_transitions)

        ordered_states = sorted(
            states_to_exit, key=lambda x: x.state and x.state.document_order or 0, reverse=True
        )
        result = OrderedSet([info.state for info in ordered_states if info.state])
        self._debug("%s States to exit: %s", self._log_id, result)

        # Update history
        for info in ordered_states:
            state = info.state
            for history in state.history:
                if history.type.is_deep:
                    history_value = [s for s in self.sm.configuration if s.is_descendant(state)]
                else:  # shallow history
                    history_value = [s for s in self.sm.configuration if s.parent == state]

                self._debug(
                    "%s Saving '%s.%s' history state: '%s'",
                    self._log_id,
                    state,
                    history,
                    [s.id for s in history_value],
                )
                self.sm.history_values[history.id] = history_value

        return ordered_states, result

    def _remove_state_from_configuration(self, state: State):
        """Remove a state from the configuration if not using atomic updates."""
        if not self.sm.atomic_configuration_update:
            self.sm._config.discard(state)

    def _execute_transition_content(
        self,
        enabled_transitions: list[Transition],
        trigger_data: TriggerData,
        get_key: Callable[[Transition], str],
        set_target_as_state: bool = False,
        **kwargs_extra,
    ):
        result = []
        for transition in enabled_transitions:
            target = transition.target if set_target_as_state else None
            args, kwargs = self._get_args_kwargs(
                transition,
                trigger_data,
                target=target,
            )
            kwargs.update(kwargs_extra)

            result += self.sm._callbacks.call(get_key(transition), *args, **kwargs)

        return result

    def _prepare_entry_states(
        self,
        enabled_transitions: list[Transition],
        states_to_exit: OrderedSet[State],
        previous_configuration: OrderedSet[State],
    ) -> _EntryPlan:
        """Compute entry set, ordering, and new configuration. Pure computation, no callbacks.

        Returns:
            (ordered_states, states_for_default_entry, default_history_content, new_configuration)
        """
        states_to_enter = OrderedSet[StateTransition]()
        states_for_default_entry = OrderedSet[StateTransition]()
        default_history_content: dict[str, Any] = {}

        self.compute_entry_set(
            enabled_transitions, states_to_enter, states_for_default_entry, default_history_content
        )

        ordered_states = sorted(
            states_to_enter, key=lambda x: x.state and x.state.document_order or 0
        )

        states_targets_to_enter = OrderedSet(info.state for info in ordered_states if info.state)

        # Build new configuration in a single pass instead of two set operations
        # (- and |) that each allocate an intermediate OrderedSet.
        new_configuration = OrderedSet(
            s for s in previous_configuration if s not in states_to_exit
        )
        new_configuration.update(states_targets_to_enter)
        self._debug("%s States to enter: %s", self._log_id, states_targets_to_enter)

        return ordered_states, states_for_default_entry, default_history_content, new_configuration

    def _add_state_to_configuration(self, target: State):
        """Add a state to the configuration if not using atomic updates."""
        if not self.sm.atomic_configuration_update:
            self.sm._config.add(target)

    def stop(self):
        """Stop this engine externally (e.g. when a parent cancels a child invocation)."""
        self._debug("%s Stopping engine", self._log_id)
        self.running = False
        try:
            self._invoke_manager.cancel_all()
        except Exception:
            self._debug("%s Error stopping engine", self._log_id, exc_info=True)

    def __del__(self):
        try:
            self._invoke_manager.cancel_all()
        except Exception:
            pass

    def _handle_final_state(self, target: State, on_entry_result: list):
        """Handle final state entry: queue done events. No direct callback dispatch."""
        self._debug("%s Reached final state: %s", self._log_id, target)
        if target.parent is None:
            self._invoke_manager.cancel_all()
            self.running = False
        else:
            parent = target.parent
            grandparent = parent.parent

            donedata_args: tuple = ()
            donedata_kwargs: dict = {}
            for item in on_entry_result:
                if not item:
                    continue
                if isinstance(item, dict):
                    donedata_kwargs.update(item)
                else:
                    donedata_args = (item,)

            BoundEvent(
                f"done.state.{parent.id}",
                _sm=self.sm,
                internal=True,
            ).put(*donedata_args, **donedata_kwargs)

            if grandparent and grandparent.parallel:
                if all(self.is_in_final_state(child) for child in grandparent.states):
                    BoundEvent(f"done.state.{grandparent.id}", _sm=self.sm, internal=True).put(
                        *donedata_args, **donedata_kwargs
                    )
                    if grandparent.parent is None:
                        self._root_parallel_final_pending = grandparent

    def _enter_states(
        self,
        enabled_transitions: list[Transition],
        trigger_data: TriggerData,
        states_to_exit: OrderedSet[State],
        previous_configuration: OrderedSet[State],
    ):
        """Enter the states as determined by the given transitions."""
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

        result = self._execute_transition_content(
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
            args, kwargs = self._get_args_kwargs(
                transition,
                trigger_data,
                target=target,
            )

            self._debug("%s Entering state: %s", self._log_id, target)
            self._add_state_to_configuration(target)

            # Execute `onentry` handlers — each handler is a separate block per
            # SCXML spec: errors in one block MUST NOT affect other blocks.
            on_entry_result = self.sm._callbacks.call(
                target.enter.key, *args, on_error=on_error, **kwargs
            )

            # Handle default initial states
            if target.id in {t.state.id for t in states_for_default_entry if t.state}:
                initial_transitions = [t for t in target.transitions if t.initial]
                if len(initial_transitions) == 1:
                    result += self.sm._callbacks.call(
                        initial_transitions[0].on.key, *args, **kwargs
                    )

            # Handle default history states
            default_history_transitions = [
                i.transition for i in default_history_content.get(target.id, [])
            ]
            if default_history_transitions:
                self._execute_transition_content(
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

    def compute_entry_set(
        self, transitions, states_to_enter, states_for_default_entry, default_history_content
    ):
        """
        Compute the set of states to be entered based on the given transitions.

        Args:
            transitions: A list of transitions.
            states_to_enter: A set to store the states that need to be entered.
            states_for_default_entry: A set to store compound states requiring default entry
            processing.
            default_history_content: A dictionary to hold temporary content for history states.
        """
        for transition in transitions:
            # Process each target state of the transition
            for target_state in transition.targets:
                info = StateTransition(transition=transition, state=target_state)
                self.add_descendant_states_to_enter(
                    info, states_to_enter, states_for_default_entry, default_history_content
                )

            # Determine the ancestor state (transition domain)
            ancestor = self.get_transition_domain(transition)

            # Add ancestor states to enter for each effective target state
            for effective_target in self.get_effective_target_states(transition):
                info = StateTransition(transition=transition, state=effective_target)
                self.add_ancestor_states_to_enter(
                    info,
                    ancestor,
                    states_to_enter,
                    states_for_default_entry,
                    default_history_content,
                )

    def add_descendant_states_to_enter(
        self,
        info: StateTransition,
        states_to_enter,
        states_for_default_entry,
        default_history_content,
    ):
        """
        Add the given state and its descendants to the entry set.

        Args:
            state: The state to add to the entry set.
            states_to_enter: A set to store the states that need to be entered.
            states_for_default_entry: A set to track compound states requiring default entry
            processing.
            default_history_content: A dictionary to hold temporary content for history states.
        """
        state = info.state

        if state and state.is_history:
            self._add_history_states_to_enter(
                info,
                cast(HistoryState, state),
                states_to_enter,
                states_for_default_entry,
                default_history_content,
            )
            return

        # Add the state to the entry set
        if self._enters_target(info.transition):
            states_to_enter.add(info)
        state = info.state

        if state.parallel:
            self._add_regions_to_enter(
                info, states_to_enter, states_for_default_entry, default_history_content
            )
        elif state.is_compound:
            self._add_initial_states_to_enter(
                info, states_to_enter, states_for_default_entry, default_history_content
            )

    def _enters_target(self, transition: Transition) -> bool:
        """Whether taking ``transition`` enters its target.

        An internal transition to its own source, or to a descendant of it, does not, unless
        the machine enables self-transition entries.
        """
        return (
            self.sm.enable_self_transition_entries
            or not transition.internal
            or not (
                transition.is_self
                or (transition.target and transition.target.is_descendant(transition.source))
            )
        )

    def _add_history_states_to_enter(
        self,
        info: StateTransition,
        state: HistoryState,
        states_to_enter,
        states_for_default_entry,
        default_history_content,
    ):
        """Add the states a history state stands for: those it recorded, or its default."""
        parent_id = state.parent and state.parent.id
        default_history_content[parent_id] = [info]
        if state.id in self.sm.history_values:
            self._debug(
                "%s History state '%s.%s' %s restoring: '%s'",
                self._log_id,
                state.parent,
                state,
                state.type.value,
                [s.id for s in self.sm.history_values[state.id]],
            )
            for history_state in self.sm.history_values[state.id]:
                info_to_add = StateTransition(transition=info.transition, state=history_state)
                if state.type.is_deep:
                    states_to_enter.add(info_to_add)
                else:
                    self.add_descendant_states_to_enter(
                        info_to_add,
                        states_to_enter,
                        states_for_default_entry,
                        default_history_content,
                    )
            for history_state in self.sm.history_values[state.id]:
                info_to_add = StateTransition(transition=info.transition, state=history_state)
                self.add_ancestor_states_to_enter(
                    info_to_add,
                    state.parent,
                    states_to_enter,
                    states_for_default_entry,
                    default_history_content,
                )
        else:
            # Handle default history content
            self._debug(
                "%s History state '%s.%s' default content: %s",
                self._log_id,
                state.parent,
                state,
                [t.target.id for t in state.transitions if t.target],
            )

            for transition in state.transitions:
                target = cast(State, transition.target)
                info_history = StateTransition(transition=transition, state=target)
                default_history_content[parent_id].append(info_history)
                self.add_descendant_states_to_enter(
                    info_history,
                    states_to_enter,
                    states_for_default_entry,
                    default_history_content,
                )
            for transition in state.transitions:
                target = cast(State, transition.target)
                info_history = StateTransition(transition=transition, state=target)

                self.add_ancestor_states_to_enter(
                    info_history,
                    state.parent,
                    states_to_enter,
                    states_for_default_entry,
                    default_history_content,
                )

    def _add_regions_to_enter(
        self,
        info: StateTransition,
        states_to_enter,
        states_for_default_entry,
        default_history_content,
    ):
        """Add each region of a parallel state, unless a state inside it is already entered."""
        for child_state in info.state.states:
            if not any(s.state.is_descendant(child_state) for s in states_to_enter):
                info_to_add = StateTransition(transition=info.transition, state=child_state)
                self.add_descendant_states_to_enter(
                    info_to_add,
                    states_to_enter,
                    states_for_default_entry,
                    default_history_content,
                )

    def _add_initial_states_to_enter(
        self,
        info: StateTransition,
        states_to_enter,
        states_for_default_entry,
        default_history_content,
    ):
        """Add the states a compound state's initial transition targets."""
        state = info.state
        states_for_default_entry.add(info)
        transition = next(t for t in state.transitions if t.initial)
        # Process all targets (supports multi-target initial transitions for parallel regions)
        for initial_target in transition.targets:
            info_initial = StateTransition(transition=transition, state=initial_target)
            self.add_descendant_states_to_enter(
                info_initial,
                states_to_enter,
                states_for_default_entry,
                default_history_content,
            )
        for initial_target in transition.targets:
            info_initial = StateTransition(transition=transition, state=initial_target)
            self.add_ancestor_states_to_enter(
                info_initial,
                state,
                states_to_enter,
                states_for_default_entry,
                default_history_content,
            )

    def add_ancestor_states_to_enter(
        self,
        info: StateTransition,
        ancestor,
        states_to_enter,
        states_for_default_entry,
        default_history_content,
    ):
        """
        Add ancestors of the given state to the entry set.

        Args:
            state: The state whose ancestors are to be added.
            ancestor: The upper bound ancestor (exclusive) to stop at.
            states_to_enter: A set to store the states that need to be entered.
            states_for_default_entry: A set to track compound states requiring default entry
            processing.
            default_history_content: A dictionary to hold temporary content for history states.
        """
        state = info.state
        assert state
        for anc in state.ancestors(parent=ancestor):
            # Add the ancestor to the entry set
            info_to_add = StateTransition(transition=info.transition, state=anc)
            states_to_enter.add(info_to_add)

            if anc.parallel:
                # Handle parallel states
                for child in anc.states:
                    if not any(s.state.is_descendant(child) for s in states_to_enter):
                        info_to_add = StateTransition(transition=info.transition, state=child)
                        self.add_descendant_states_to_enter(
                            info_to_add,
                            states_to_enter,
                            states_for_default_entry,
                            default_history_content,
                        )

    def _check_root_final_state(self):
        """SCXML spec: terminate when the root configuration is final.

        For top-level parallel states, the machine terminates when all child
        regions have reached their final states — equivalent to the SCXML
        algorithm's ``isInFinalState(scxml_element)`` check.

        Uses a flag set by ``_handle_final_state`` (Information Expert) to
        avoid re-scanning top-level states on every macrostep.  The flag is
        deferred because ``done.state`` events queued by ``_handle_final_state``
        may trigger transitions that exit the parallel, so we verify the
        parallel is still in the configuration before terminating.
        """
        state = self._root_parallel_final_pending
        if state is None:
            return
        self._root_parallel_final_pending = None
        # A done.state transition may have exited the parallel; verify it's
        # still in the configuration before terminating.
        if state in self.sm.configuration and self.is_in_final_state(state):
            self._invoke_manager.cancel_all()
            self.running = False

    def is_in_final_state(self, state: State) -> bool:
        """Whether every region of a parallel state, or a compound state, rests in a final child.

        An atomic state has no children, so it never does.
        """
        if state.parallel:
            return all(self.is_in_final_state(s) for s in state.states)
        return any(s.final and s in self.sm.configuration for s in state.states)
