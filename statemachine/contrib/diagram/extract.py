from typing import TYPE_CHECKING
from typing import List
from typing import Set
from typing import Union

from .model import ActionType
from .model import DiagramAction
from .model import DiagramGraph
from .model import DiagramState
from .model import DiagramTransition
from .model import StateType

if TYPE_CHECKING:
    from statemachine.state import State
    from statemachine.statemachine import StateChart
    from statemachine.transition import Transition

    # A StateChart class or instance — both expose the same structural metadata.
    MachineRef = Union["StateChart", "type[StateChart]"]


def _determine_state_type(state: "State") -> StateType:
    from statemachine.state import HistoryState
    from statemachine.state import HistoryType

    if isinstance(state, HistoryState):
        if state.type == HistoryType.DEEP:
            return StateType.HISTORY_DEEP
        return StateType.HISTORY_SHALLOW
    if getattr(state, "parallel", False):
        return StateType.PARALLEL
    if state.final:
        return StateType.FINAL
    return StateType.REGULAR


def _actions_getter(machine: "MachineRef"):
    from statemachine.statemachine import StateChart

    if isinstance(machine, StateChart):

        def getter(grouper):  # pyright: ignore[reportRedeclaration]
            return machine._callbacks.str(grouper.key)
    else:

        def getter(grouper):
            all_names = set(dir(machine))
            return ", ".join(str(c) for c in grouper if not c.is_convention or c.func in all_names)

    return getter


def _extract_state_actions(state: "State", getter) -> List[DiagramAction]:
    actions: List[DiagramAction] = []

    entry = str(getter(state.enter))
    exit_ = str(getter(state.exit))

    if entry:
        actions.append(DiagramAction(type=ActionType.ENTRY, body=entry))
    if exit_:
        actions.append(DiagramAction(type=ActionType.EXIT, body=exit_))

    for transition in state.transitions:
        if transition.internal:
            on_text = str(getter(transition.on))
            if on_text:
                actions.append(
                    DiagramAction(type=ActionType.INTERNAL, body=f"{transition.event} / {on_text}")
                )

    return actions


def _extract_state(
    state: "State",
    machine: "MachineRef",
    getter,
    active_values: set,
) -> DiagramState:
    state_type = _determine_state_type(state)
    is_active = state.value in active_values
    is_parallel_area = bool(state.parent and getattr(state.parent, "parallel", False))

    children: List[DiagramState] = []
    for substate in state.states:
        children.append(_extract_state(substate, machine, getter, active_values))
    for history_state in getattr(state, "history", []):
        children.append(_extract_state(history_state, machine, getter, active_values))

    actions = _extract_state_actions(state, getter)

    return DiagramState(
        id=state.id,
        name=state.name,
        type=state_type,
        actions=actions,
        children=children,
        is_active=is_active,
        is_parallel_area=is_parallel_area,
        is_initial=getattr(state, "initial", False),
    )


def _format_event_names(transition: "Transition") -> str:
    """Build a display string for the events that trigger a transition.

    ``_expand_event_id`` registers both the Python attribute name
    (``done_invoke_X``) and the SCXML dot form (``done.invoke.X``) under the
    same transition.  For diagram display we only want unique *semantic* events,
    keeping the Python attribute name when an alias pair exists.
    """
    events = list(transition.events)
    if not events:
        return ""

    all_ids = {str(e) for e in events}

    display: List[str] = []
    for event in events:
        eid = str(event)
        # Skip dot-form aliases (e.g. "done.invoke.X") when the underscore
        # form ("done_invoke_X") is also registered on this transition.
        if "." in eid and eid.replace(".", "_") in all_ids:
            continue
        if eid not in display:  # pragma: no branch
            display.append(eid)

    return " ".join(display)


def _extract_transitions_from_state(state: "State") -> List[DiagramTransition]:
    """Extract transitions from a single state (non-recursive)."""
    result: List[DiagramTransition] = []
    for transition in state.transitions:
        targets = transition.targets if transition.targets else []
        target_ids = [t.id for t in targets]

        cond_strs = [str(c) for c in transition.cond]

        result.append(
            DiagramTransition(
                source=transition.source.id,
                targets=target_ids,
                event=_format_event_names(transition),
                guards=cond_strs,
                is_internal=transition.internal,
            )
        )
    return result


def _extract_all_transitions(states) -> List[DiagramTransition]:
    """Recursively extract transitions from all states."""
    result: List[DiagramTransition] = []
    for state in states:
        result.extend(_extract_transitions_from_state(state))
        if state.states:
            result.extend(_extract_all_transitions(state.states))
        for history_state in getattr(state, "history", []):
            result.extend(_extract_transitions_from_state(history_state))
            if history_state.states:  # pragma: no cover
                result.extend(_extract_all_transitions(history_state.states))
    return result


def _collect_compound_ids(states: List[DiagramState]) -> Set[str]:
    """Collect IDs of states that have children (compound/parallel)."""
    result: Set[str] = set()
    for state in states:
        if state.children:
            result.add(state.id)
        result.update(_collect_compound_ids(state.children))
    return result


def _collect_bidirectional_compound_ids(
    transitions: List[DiagramTransition],
    compound_ids: Set[str],
) -> Set[str]:
    """Find compound states that have both outgoing and incoming explicit edges."""
    outgoing: Set[str] = set()
    incoming: Set[str] = set()
    for t in transitions:
        if t.is_internal:
            continue
        # Skip implicit initial transitions
        if t.source in compound_ids and not t.event and t.targets:
            continue
        if t.source in compound_ids:
            outgoing.add(t.source)
        for target_id in t.targets:
            if target_id in compound_ids:
                incoming.add(target_id)
    return outgoing & incoming


def _mark_initial_transitions(
    transitions: List[DiagramTransition],
    compound_ids: Set[str],
) -> None:
    """Mark implicit initial transitions (compound state → child, no event)."""
    for t in transitions:
        if t.source in compound_ids and not t.event and t.targets and not t.is_internal:
            t.is_initial = True


def _resolve_initial_states(states: List[DiagramState]) -> None:
    """Ensure exactly one state per level has is_initial=True.

    Skips parallel areas and history states. Falls back to document order
    (first non-history, non-parallel-area state) when no explicit initial exists.
    Recurses into children.

    Parallel areas (children of a parallel state) have their is_initial flag
    cleared: all regions are auto-activated, so no initial arrow is needed.
    """
    # Clear is_initial on parallel areas — all children of a parallel state
    # are simultaneously active; initial arrows would be misleading.
    for s in states:
        if s.is_parallel_area:
            s.is_initial = False

    candidates = [
        s
        for s in states
        if s.type not in (StateType.HISTORY_SHALLOW, StateType.HISTORY_DEEP)
        and not s.is_parallel_area
    ]

    has_explicit_initial = any(s.is_initial for s in candidates)
    if not has_explicit_initial and candidates:
        candidates[0].is_initial = True

    for state in states:
        if state.children:
            _resolve_initial_states(state.children)


def extract(machine_or_class: "MachineRef") -> DiagramGraph:
    """Extract a DiagramGraph IR from a state machine instance or class.

    Accepts either a class or an instance.  The class is **never** instantiated
    — all structural metadata (states, transitions, name) is available on the
    class itself thanks to the metaclass.  Active-state highlighting is only
    produced when an *instance* is passed.

    Args:
        machine_or_class: A StateMachine/StateChart instance or class.

    Returns:
        A DiagramGraph representing the machine's structure.
    """
    from statemachine.statemachine import StateChart

    if isinstance(machine_or_class, StateChart):
        machine: "MachineRef" = machine_or_class
    elif isinstance(machine_or_class, type) and issubclass(machine_or_class, StateChart):
        machine = machine_or_class
    else:
        raise TypeError(f"Expected a StateChart instance or class, got {type(machine_or_class)}")

    getter = _actions_getter(machine)

    active_values: set = set()
    if isinstance(machine, StateChart) and hasattr(machine, "configuration_values"):
        active_values = set(machine.configuration_values)

    states: List[DiagramState] = []
    for state in machine.states:
        states.append(_extract_state(state, machine, getter, active_values))

    transitions = _extract_all_transitions(machine.states)

    compound_ids = _collect_compound_ids(states)
    bidir_ids = _collect_bidirectional_compound_ids(transitions, compound_ids)
    _mark_initial_transitions(transitions, compound_ids)
    _resolve_initial_states(states)

    return DiagramGraph(
        name=machine.name,
        states=states,
        transitions=transitions,
        compound_state_ids=compound_ids,
        bidirectional_compound_ids=bidir_ids,
    )
