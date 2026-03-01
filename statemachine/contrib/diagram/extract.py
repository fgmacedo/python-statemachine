from typing import TYPE_CHECKING
from typing import List

from .model import DiagramAction
from .model import DiagramGraph
from .model import DiagramState
from .model import DiagramTransition
from .model import StateType

if TYPE_CHECKING:
    from statemachine.state import State
    from statemachine.statemachine import StateChart


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


def _actions_getter(machine: "StateChart"):
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
        actions.append(DiagramAction(type="entry", body=entry))
    if exit_:
        actions.append(DiagramAction(type="exit", body=exit_))

    for transition in state.transitions:
        if transition.internal:
            on_text = str(getter(transition.on))
            if on_text:
                actions.append(
                    DiagramAction(type="internal", body=f"{transition.event} / {on_text}")
                )

    return actions


def _extract_state(
    state: "State",
    machine: "StateChart",
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
    )


def _extract_transitions_from_state(state: "State", getter) -> List[DiagramTransition]:
    """Extract transitions from a single state (non-recursive)."""
    result: List[DiagramTransition] = []
    for transition in state.transitions:
        targets = transition.targets if transition.targets else []
        target_ids = [t.id for t in targets]
        primary_target = target_ids[0] if target_ids else None

        cond_strs = [str(c) for c in transition.cond]

        result.append(
            DiagramTransition(
                source=transition.source.id,
                target=primary_target,
                targets=target_ids,
                event=transition.event,
                guards=cond_strs,
                is_internal=transition.internal,
            )
        )
    return result


def _extract_all_transitions(states, getter) -> List[DiagramTransition]:
    """Recursively extract transitions from all states."""
    result: List[DiagramTransition] = []
    for state in states:
        result.extend(_extract_transitions_from_state(state, getter))
        if state.states:
            result.extend(_extract_all_transitions(state.states, getter))
        for history_state in getattr(state, "history", []):
            result.extend(_extract_transitions_from_state(history_state, getter))
            if history_state.states:
                result.extend(_extract_all_transitions(history_state.states, getter))
    return result


def extract(machine_or_class: "StateChart | type") -> DiagramGraph:
    """Extract a DiagramGraph IR from a state machine instance or class.

    Args:
        machine_or_class: A StateMachine/StateChart instance or class.

    Returns:
        A DiagramGraph representing the machine's structure.
    """
    from statemachine.statemachine import StateChart

    is_class = isinstance(machine_or_class, type)
    if is_class and issubclass(machine_or_class, StateChart):  # type: ignore[arg-type]
        machine = machine_or_class()  # type: ignore[operator]
    elif isinstance(machine_or_class, StateChart):
        machine = machine_or_class
    else:
        raise TypeError(f"Expected a StateChart instance or class, got {type(machine_or_class)}")

    getter = _actions_getter(machine)
    active_values: set = set()
    if not is_class and hasattr(machine, "configuration_values"):
        active_values = set(machine.configuration_values)

    states: List[DiagramState] = []
    for state in machine.states:
        states.append(_extract_state(state, machine, getter, active_values))

    transitions = _extract_all_transitions(machine.states, getter)

    return DiagramGraph(
        name=machine.name,
        states=states,
        transitions=transitions,
    )
