import logging
from dataclasses import dataclass
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
from weakref import proxy

from ..event import BoundEvent
from ..event import Event
from ..event_data import EventData
from ..event_data import TriggerData
from ..exceptions import TransitionNotAllowed
from ..orderedset import OrderedSet
from ..state import State
from ..transition import Transition

if TYPE_CHECKING:
    from ..statemachine import StateMachine

logger = logging.getLogger(__name__)


@dataclass(frozen=True, unsafe_hash=True)
class StateTransition:
    transition: Transition
    source: "State | None" = None
    target: "State | None" = None


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
    def __init__(self, sm: "StateMachine"):
        self.sm: StateMachine = proxy(sm)
        self.external_queue = EventQueue()
        self.internal_queue = EventQueue()
        self._sentinel = object()
        self.running = True
        self._processing = Lock()

    def empty(self):
        return self.external_queue.is_empty()

    def put(self, trigger_data: TriggerData, internal: bool = False):
        """Put the trigger on the queue without blocking the caller."""
        if not self.running and not self.sm.allow_event_without_transition:
            raise TransitionNotAllowed(trigger_data.event, self.sm.configuration)

        if internal:
            self.internal_queue.put(trigger_data)
        else:
            self.external_queue.put(trigger_data)

    def pop(self):
        return self.external_queue.pop()

    def clear(self):
        self.external_queue.clear()

    def cancel_event(self, send_id: str):
        """Cancel the event with the given send_id."""
        self.external_queue.remove(send_id)

    def start(self):
        if self.sm.current_state_value is not None:
            return

        BoundEvent("__initial__", _sm=self.sm).put()

    def _initial_transition(self, trigger_data):
        transition = Transition(State(), self.sm._get_initial_state(), event="__initial__")
        transition._specs.clear()
        return transition

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
            if transition.target is None:
                continue
            domain = self.get_transition_domain(transition)
            for state in self.sm.configuration:
                if domain is None or state.is_descendant(domain):
                    info = StateTransition(
                        transition=transition, source=state, target=transition.target
                    )
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
        elif transition.internal and transition.is_self and transition.target.is_atomic:
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
        # TODO: Handle history states
        return OrderedSet([transition.target])

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
        result = self._execute_transition_content(
            transitions, trigger_data, lambda t: t.before.key
        )

        states_to_exit = self._exit_states(transitions, trigger_data)
        logger.debug("States to exit: %s", states_to_exit)
        result += self._execute_transition_content(transitions, trigger_data, lambda t: t.on.key)
        self._enter_states(transitions, trigger_data, states_to_exit)
        self._execute_transition_content(
            transitions,
            trigger_data,
            lambda t: t.after.key,
            set_target_as_state=True,
        )

        if len(result) == 0:
            result = None
        elif len(result) == 1:
            result = result[0]

        return result

    def _get_args_kwargs(
        self, transition: Transition, trigger_data: TriggerData, set_target_as_state: bool = False
    ):
        # TODO: Ideally this method should be called only once per microstep/transition
        event_data = EventData(trigger_data=trigger_data, transition=transition)
        if set_target_as_state:
            event_data.state = transition.target

        args, kwargs = event_data.args, event_data.extended_kwargs

        result = self.sm._callbacks.call(self.sm.prepare.key, *args, **kwargs)
        for new_kwargs in result:
            kwargs.update(new_kwargs)
        return args, kwargs

    def _conditions_match(self, transition: Transition, trigger_data: TriggerData):
        args, kwargs = self._get_args_kwargs(transition, trigger_data)

        self.sm._callbacks.call(transition.validators.key, *args, **kwargs)
        return self.sm._callbacks.all(transition.cond.key, *args, **kwargs)

    def _exit_states(self, enabled_transitions: List[Transition], trigger_data: TriggerData):
        """Compute and process the states to exit for the given transitions."""
        states_to_exit = self._compute_exit_set(enabled_transitions)

        # # TODO: Remove states from states_to_invoke
        # for state in states_to_exit:
        #     self.states_to_invoke.discard(state)

        # TODO: Sort states to exit in exit order
        # states_to_exit = sorted(states_to_exit, key=self.exit_order)

        for info in states_to_exit:
            args, kwargs = self._get_args_kwargs(info.transition, trigger_data)

            # # TODO: Update history
            # for history in state.history:
            #     if history.type == "deep":
            #         history_value = [s for s in self.sm.configuration if self.is_descendant(s, state)] # noqa: E501
            #     else:  # shallow history
            #         history_value = [s for s in self.sm.configuration if s.parent == state]
            #     self.history_values[history.id] = history_value

            # Execute `onexit` handlers
            if info.source is not None:  # TODO: and not info.transition.internal:
                self.sm._callbacks.call(info.source.exit.key, *args, **kwargs)

            # TODO: Cancel invocations
            # for invocation in state.invoke:
            #     self.cancel_invoke(invocation)

            # Remove state from configuration
            # self.sm.configuration -= {info.source}  # .discard(info.source)

        return OrderedSet([info.source for info in states_to_exit])

    def _execute_transition_content(
        self,
        enabled_transitions: List[Transition],
        trigger_data: TriggerData,
        get_key: Callable[[Transition], str],
        set_target_as_state: bool = False,
    ):
        result = []
        for transition in enabled_transitions:
            args, kwargs = self._get_args_kwargs(
                transition, trigger_data, set_target_as_state=set_target_as_state
            )

            result += self.sm._callbacks.call(get_key(transition), *args, **kwargs)

        return result

    def _enter_states(
        self,
        enabled_transitions: List[Transition],
        trigger_data: TriggerData,
        states_to_exit: OrderedSet[State],
    ):
        """Enter the states as determined by the given transitions."""
        states_to_enter = OrderedSet[StateTransition]()
        states_for_default_entry = OrderedSet[StateTransition]()
        default_history_content: Dict[str, Any] = {}

        # Compute the set of states to enter
        self.compute_entry_set(
            enabled_transitions, states_to_enter, states_for_default_entry, default_history_content
        )

        # We update the configuration atomically
        states_targets_to_enter = OrderedSet(
            info.target for info in states_to_enter if info.target
        )
        logger.debug("States to enter: %s", states_targets_to_enter)

        configuration = self.sm.configuration
        self.sm.configuration = cast(
            OrderedSet[State], (configuration - states_to_exit) | states_targets_to_enter
        )

        # Sort states to enter in entry order
        # for state in sorted(states_to_enter, key=self.entry_order):   # TODO: order of states_to_enter # noqa: E501
        for info in states_to_enter:
            target = info.target
            assert target
            transition = info.transition
            args, kwargs = self._get_args_kwargs(
                transition, trigger_data, set_target_as_state=True
            )

            # Add state to the configuration
            # self.sm.configuration |= {target}

            # TODO: Add state to states_to_invoke
            # self.states_to_invoke.add(state)

            # Initialize data model if using late binding
            # if self.binding == "late" and state.is_first_entry:
            #     self.initialize_data_model(state)
            #     state.is_first_entry = False

            # Execute `onentry` handlers
            self.sm._callbacks.call(target.enter.key, *args, **kwargs)

            # Handle default initial states
            # TODO: Handle default initial states
            # if state in states_for_default_entry:
            #     self.execute_content(state.initial.transition)

            # Handle default history states
            # if state.id in default_history_content:
            #     self.execute_content(default_history_content[state.id])

            # Handle final states
            if target.final:
                if target.parent is None:
                    self.running = False
                else:
                    parent = target.parent
                    grandparent = parent.parent

                    BoundEvent(
                        f"done.state.{parent.id}",
                        _sm=self.sm,
                        internal=True,
                    ).put()

                    if grandparent.parallel:
                        if all(child.final for child in grandparent.states):
                            BoundEvent(f"done.state.{parent.id}", _sm=self.sm, internal=True).put()

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
            for target_state in [transition.target]:
                info = StateTransition(
                    transition=transition, target=target_state, source=transition.source
                )
                self.add_descendant_states_to_enter(
                    info, states_to_enter, states_for_default_entry, default_history_content
                )

            # Determine the ancestor state (transition domain)
            ancestor = self.get_transition_domain(transition)

            # Add ancestor states to enter for each effective target state
            for effective_target in self.get_effective_target_states(transition):
                info = StateTransition(
                    transition=transition, target=effective_target, source=transition.source
                )
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
        # if self.is_history_state(state):
        #     # Handle history state
        #     if state.id in self.history_values:
        #         for history_state in self.history_values[state.id]:
        #             self.add_descendant_states_to_enter(history_state, states_to_enter, states_for_default_entry, default_history_content)  # noqa: E501
        #         for history_state in self.history_values[state.id]:
        #             self.add_ancestor_states_to_enter(history_state, state.parent, states_to_enter, states_for_default_entry, default_history_content)  # noqa: E501
        #     else:
        #         # Handle default history content
        #         default_history_content[state.parent.id] = state.transition.content
        #         for target_state in state.transition.target:
        #             self.add_descendant_states_to_enter(target_state, states_to_enter, states_for_default_entry, default_history_content)  # noqa: E501
        #         for target_state in state.transition.target:
        #             self.add_ancestor_states_to_enter(target_state, state.parent, states_to_enter, states_for_default_entry, default_history_content)  # noqa: E501
        #     return

        # Add the state to the entry set
        if (
            not self.sm.enable_self_transition_entries
            and info.transition.internal
            and (
                info.transition.is_self
                or info.transition.target.is_descendant(info.transition.source)
            )
        ):
            pass
        else:
            states_to_enter.add(info)
        state = info.target
        assert state

        if state.parallel:
            for child_state in state.states:
                if not any(s.target.is_descendant(child_state) for s in states_to_enter):
                    info_to_add = StateTransition(
                        transition=info.transition,
                        target=child_state,
                        source=info.transition.source,
                    )
                    self.add_descendant_states_to_enter(
                        info_to_add,
                        states_to_enter,
                        states_for_default_entry,
                        default_history_content,
                    )
        elif state.is_compound:
            states_for_default_entry.add(info)
            initial_state = next(s for s in state.states if s.initial)
            transition = next(
                t for t in state.transitions if t.initial and t.target == initial_state
            )
            info_initial = StateTransition(
                transition=transition,
                target=transition.target,
                source=transition.source,
            )
            self.add_descendant_states_to_enter(
                info_initial,
                states_to_enter,
                states_for_default_entry,
                default_history_content,
            )

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
        state = info.target
        assert state
        for anc in state.ancestors(parent=ancestor):
            # Add the ancestor to the entry set
            info_to_add = StateTransition(
                transition=info.transition,
                target=anc,
                source=info.transition.source,
            )
            states_to_enter.add(info_to_add)

            if anc.parallel:
                # Handle parallel states
                for child in anc.states:
                    if not any(s.target.is_descendant(child) for s in states_to_enter):
                        info_to_add = StateTransition(
                            transition=info.transition,
                            target=child,
                            source=info.transition.source,
                        )
                        self.add_descendant_states_to_enter(
                            info_to_add,
                            states_to_enter,
                            states_for_default_entry,
                            default_history_content,
                        )
