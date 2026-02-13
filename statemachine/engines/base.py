import logging
from dataclasses import dataclass
from dataclasses import field
from itertools import chain
from queue import PriorityQueue
from queue import Queue
from threading import Lock
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import cast
from weakref import ReferenceType
from weakref import ref

from ..event import BoundEvent
from ..event import Event
from ..event_data import EventData
from ..event_data import TriggerData
from ..exceptions import InvalidDefinition
from ..exceptions import TransitionNotAllowed
from ..orderedset import OrderedSet
from ..state import HistoryState
from ..state import State
from ..transition import Transition

if TYPE_CHECKING:
    from ..statemachine import StateChart

logger = logging.getLogger(__name__)


@dataclass(frozen=True, unsafe_hash=True, eq=True)
class StateTransition:
    transition: Transition = field(compare=False)
    state: State


class EventQueue:
    def __init__(self):
        self.queue: Queue = PriorityQueue()

    def __repr__(self):
        return f"EventQueue({self.queue.queue!r}, size={self.queue.qsize()})"

    def is_empty(self):
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
    def __init__(self, sm: "StateChart"):
        self._sm: ReferenceType["StateChart"] = ref(sm)
        self.external_queue = EventQueue()
        self.internal_queue = EventQueue()
        self._sentinel = object()
        self.running = True
        self._processing = Lock()
        self._cache: Dict = {}  # Cache for _get_args_kwargs results

    def empty(self):
        return self.external_queue.is_empty()

    @property
    def sm(self) -> "StateChart":
        sm = self._sm()
        assert sm, "StateMachine has been destroyed"
        return sm

    def clear_cache(self):
        """Clears the cache. Should be called at the start of each processing loop."""
        self._cache.clear()

    def put(self, trigger_data: TriggerData, internal: bool = False, _delayed: bool = False):
        """Put the trigger on the queue without blocking the caller."""
        if not self.running and not self.sm.allow_event_without_transition:
            raise TransitionNotAllowed(trigger_data.event, self.sm.configuration)

        if internal:
            self.internal_queue.put(trigger_data)
        else:
            self.external_queue.put(trigger_data)

        if not _delayed:
            logger.debug(
                "New event '%s' put on the '%s' queue",
                trigger_data.event,
                "internal" if internal else "external",
            )

    def pop(self):
        return self.external_queue.pop()

    def clear(self):
        self.external_queue.clear()

    def cancel_event(self, send_id: str):
        """Cancel the event with the given send_id."""
        self.external_queue.remove(send_id)

    def _on_error_handler(self, trigger_data: TriggerData) -> "Callable[[Exception], None] | None":
        """Return a per-block error handler bound to *trigger_data*, or ``None``.

        When ``error_on_execution`` is enabled, returns a callable that queues
        ``error.execution`` on the internal queue.  Otherwise returns ``None``
        so that exceptions propagate normally.
        """
        if not self.sm.error_on_execution:
            return None

        def handler(error: Exception) -> None:
            if isinstance(error, InvalidDefinition):
                raise error
            # Per-block errors always queue error.execution — even when the current
            # event is itself error.execution.  The SCXML spec mandates that the
            # new error.execution is a separate event that may trigger a different
            # transition (see W3C test 152).  The infinite-loop guard lives at the
            # *microstep* level (in ``_send_error_execution``), not here.
            self.sm.send("error.execution", error=error, internal=True)

        return handler

    def _handle_error(self, error: Exception, trigger_data: TriggerData):
        """Handle an execution error: send ``error.execution`` or re-raise.

        Centralises the ``if error_on_execution`` check so callers don't need
        to know about the variation.
        """
        if self.sm.error_on_execution:
            self._send_error_execution(error, trigger_data)
        else:
            raise error

    def _send_error_execution(self, error: Exception, trigger_data: TriggerData):
        """Send error.execution to internal queue (SCXML spec).

        If already processing an error.execution event, ignore to avoid infinite loops.
        """
        logger.debug("Error %s captured while executing event=%s", error, trigger_data.event)
        if trigger_data.event and str(trigger_data.event) == "error.execution":
            logger.warning("Error while processing error.execution, ignoring: %s", error)
            return
        self.sm.send("error.execution", error=error, internal=True)

    def start(self):
        if self.sm.current_state_value is not None:
            return

        BoundEvent("__initial__", _sm=self.sm).put()

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

    def _compute_exit_set(self, transitions: List[Transition]) -> OrderedSet[StateTransition]:
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
    def find_lcca(states: List[State]) -> "State | None":
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

    def _select_transitions(
        self, trigger_data: TriggerData, predicate: Callable
    ) -> OrderedSet[Transition]:
        """Select the transitions that match the trigger data."""
        enabled_transitions = OrderedSet[Transition]()

        # Get atomic states, TODO: sorted by document order
        atomic_states = (state for state in self.sm.configuration if state.is_atomic)

        def first_transition_that_matches(
            state: State, event: "Event | None"
        ) -> "Transition | None":
            for s in chain([state], state.ancestors()):
                transition: Transition
                for transition in s.transitions:
                    if (
                        not transition.initial
                        and predicate(transition, event)
                        and self._conditions_match(transition, trigger_data)
                    ):
                        return transition

            return None

        for state in atomic_states:
            transition = first_transition_that_matches(state, trigger_data.event)
            if transition is not None:
                enabled_transitions.add(transition)

        return self._filter_conflicting_transitions(enabled_transitions)

    def microstep(self, transitions: List[Transition], trigger_data: TriggerData):
        """Process a single set of transitions in a 'lock step'.
        This includes exiting states, executing transition content, and entering states.
        """
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

    def _get_args_kwargs(
        self, transition: Transition, trigger_data: TriggerData, target: "State | None" = None
    ):
        # Generate a unique key for the cache, the cache is invalidated once per loop
        cache_key = (id(transition), id(trigger_data), id(target))

        # Check the cache for existing results
        if cache_key in self._cache:
            return self._cache[cache_key]

        event_data = EventData(trigger_data=trigger_data, transition=transition)
        if target:
            event_data.state = target
            event_data.target = target

        args, kwargs = event_data.args, event_data.extended_kwargs

        result = self.sm._callbacks.call(self.sm.prepare.key, *args, **kwargs)
        for new_kwargs in result:
            kwargs.update(new_kwargs)

        # Store the result in the cache
        self._cache[cache_key] = (args, kwargs)
        return args, kwargs

    def _conditions_match(self, transition: Transition, trigger_data: TriggerData):
        args, kwargs = self._get_args_kwargs(transition, trigger_data)
        on_error = self._on_error_handler(trigger_data)

        self.sm._callbacks.call(transition.validators.key, *args, on_error=on_error, **kwargs)
        return self.sm._callbacks.all(transition.cond.key, *args, on_error=on_error, **kwargs)

    def _prepare_exit_states(
        self,
        enabled_transitions: List[Transition],
    ) -> "tuple[list[StateTransition], OrderedSet[State]]":
        """Compute exit set, sort, and update history. Pure computation, no callbacks."""
        states_to_exit = self._compute_exit_set(enabled_transitions)

        ordered_states = sorted(
            states_to_exit, key=lambda x: x.state and x.state.document_order or 0, reverse=True
        )
        result = OrderedSet([info.state for info in ordered_states if info.state])
        logger.debug("States to exit: %s", result)

        # Update history
        for info in ordered_states:
            state = info.state
            for history in state.history:
                if history.deep:
                    history_value = [s for s in self.sm.configuration if s.is_descendant(state)]  # noqa: E501
                else:  # shallow history
                    history_value = [s for s in self.sm.configuration if s.parent == state]

                logger.debug(
                    "Saving '%s.%s' history state: '%s'",
                    state,
                    history,
                    [s.id for s in history_value],
                )
                self.sm.history_values[history.id] = history_value

        return ordered_states, result

    def _remove_state_from_configuration(self, state: State):
        """Remove a state from the configuration if not using atomic updates."""
        if not self.sm.atomic_configuration_update:
            self.sm.configuration -= {state}

    def _exit_states(
        self, enabled_transitions: List[Transition], trigger_data: TriggerData
    ) -> OrderedSet[State]:
        """Compute and process the states to exit for the given transitions."""
        ordered_states, result = self._prepare_exit_states(enabled_transitions)
        on_error = self._on_error_handler(trigger_data)

        for info in ordered_states:
            args, kwargs = self._get_args_kwargs(info.transition, trigger_data)

            # Execute `onexit` handlers — same per-block error isolation as onentry.
            if info.state is not None:  # TODO: and not info.transition.internal:
                self.sm._callbacks.call(info.state.exit.key, *args, on_error=on_error, **kwargs)

            self._remove_state_from_configuration(info.state)

        return result

    def _execute_transition_content(
        self,
        enabled_transitions: List[Transition],
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
        enabled_transitions: List[Transition],
        states_to_exit: OrderedSet[State],
        previous_configuration: OrderedSet[State],
    ) -> "tuple[list[StateTransition], OrderedSet[StateTransition], Dict[str, Any], OrderedSet[State]]":  # noqa: E501
        """Compute entry set, ordering, and new configuration. Pure computation, no callbacks.

        Returns:
            (ordered_states, states_for_default_entry, default_history_content, new_configuration)
        """
        states_to_enter = OrderedSet[StateTransition]()
        states_for_default_entry = OrderedSet[StateTransition]()
        default_history_content: Dict[str, Any] = {}

        self.compute_entry_set(
            enabled_transitions, states_to_enter, states_for_default_entry, default_history_content
        )

        ordered_states = sorted(
            states_to_enter, key=lambda x: x.state and x.state.document_order or 0
        )

        states_targets_to_enter = OrderedSet(info.state for info in ordered_states if info.state)

        new_configuration = cast(
            OrderedSet[State], (previous_configuration - states_to_exit) | states_targets_to_enter
        )
        logger.debug("States to enter: %s", states_targets_to_enter)

        return ordered_states, states_for_default_entry, default_history_content, new_configuration

    def _add_state_to_configuration(self, target: State):
        """Add a state to the configuration if not using atomic updates."""
        if not self.sm.atomic_configuration_update:
            self.sm.configuration |= {target}

    def _handle_final_state(self, target: State, on_entry_result: list):
        """Handle final state entry: queue done events. No direct callback dispatch."""
        if target.parent is None:
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

    def _enter_states(  # noqa: C901
        self,
        enabled_transitions: List[Transition],
        trigger_data: TriggerData,
        states_to_exit: OrderedSet[State],
        previous_configuration: OrderedSet[State],
    ):
        """Enter the states as determined by the given transitions."""
        on_error = self._on_error_handler(trigger_data)
        ordered_states, states_for_default_entry, default_history_content, new_configuration = (
            self._prepare_entry_states(enabled_transitions, states_to_exit, previous_configuration)
        )

        result = self._execute_transition_content(
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
            args, kwargs = self._get_args_kwargs(
                transition,
                trigger_data,
                target=target,
            )

            logger.debug("Entering state: %s", target)
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

    def add_descendant_states_to_enter(  # noqa: C901
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
            # Handle history state
            state = cast(HistoryState, state)
            parent_id = state.parent and state.parent.id
            default_history_content[parent_id] = [info]
            if state.id in self.sm.history_values:
                logger.debug(
                    "History state '%s.%s' %s restoring: '%s'",
                    state.parent,
                    state,
                    "deep" if state.deep else "shallow",
                    [s.id for s in self.sm.history_values[state.id]],
                )
                for history_state in self.sm.history_values[state.id]:
                    info_to_add = StateTransition(transition=info.transition, state=history_state)
                    if state.deep:
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
                logger.debug(
                    "History state '%s.%s' default content: %s",
                    state.parent,
                    state,
                    [t.target.id for t in state.transitions if t.target],
                )

                for transition in state.transitions:
                    info_history = StateTransition(transition=transition, state=transition.target)
                    default_history_content[parent_id].append(info_history)
                    self.add_descendant_states_to_enter(
                        info_history,
                        states_to_enter,
                        states_for_default_entry,
                        default_history_content,
                    )  # noqa: E501
                for transition in state.transitions:
                    info_history = StateTransition(transition=transition, state=transition.target)

                    self.add_ancestor_states_to_enter(
                        info_history,
                        state.parent,
                        states_to_enter,
                        states_for_default_entry,
                        default_history_content,
                    )  # noqa: E501
            return

        # Add the state to the entry set
        if (
            not self.sm.enable_self_transition_entries
            and info.transition.internal
            and (
                info.transition.is_self
                or (
                    info.transition.target
                    and info.transition.target.is_descendant(info.transition.source)
                )
            )
        ):
            pass
        else:
            states_to_enter.add(info)
        state = info.state

        if state.parallel:
            for child_state in state.states:
                if not any(s.state.is_descendant(child_state) for s in states_to_enter):
                    info_to_add = StateTransition(transition=info.transition, state=child_state)
                    self.add_descendant_states_to_enter(
                        info_to_add,
                        states_to_enter,
                        states_for_default_entry,
                        default_history_content,
                    )
        elif state.is_compound:
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

    def is_in_final_state(self, state: State) -> bool:
        if state.is_compound:
            return any(s.final and s in self.sm.configuration for s in state.states)
        elif state.parallel:  # pragma: no cover — requires nested parallel-in-parallel
            return all(self.is_in_final_state(s) for s in state.states)
        else:  # pragma: no cover — atomic states are never "in final state"
            return False
