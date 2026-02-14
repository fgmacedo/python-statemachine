from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Protocol
from typing import Sequence
from typing import Tuple
from typing import TypedDict
from typing import cast

from ..factory import StateMachineMetaclass
from ..state import HistoryState
from ..state import State
from ..statemachine import StateChart
from ..transition import Transition
from ..transition_list import TransitionList


class ActionProtocol(Protocol):
    def __call__(self, *args, **kwargs) -> Any: ...


class TransitionDict(TypedDict, total=False):
    target: "str | None"
    event: "str | None"
    internal: bool
    initial: bool
    validators: bool
    cond: "str | ActionProtocol | Sequence[str] | Sequence[ActionProtocol]"
    unless: "str | ActionProtocol | Sequence[str] | Sequence[ActionProtocol]"
    on: "str | ActionProtocol | Sequence[str] | Sequence[ActionProtocol]"
    before: "str | ActionProtocol | Sequence[str] | Sequence[ActionProtocol]"
    after: "str | ActionProtocol | Sequence[str] | Sequence[ActionProtocol]"


TransitionsDict = Dict["str | None", List[TransitionDict]]
TransitionsList = List[TransitionDict]


class BaseStateKwargs(TypedDict, total=False):
    name: str
    value: Any
    initial: bool
    final: bool
    parallel: bool
    enter: "str | ActionProtocol | Sequence[str] | Sequence[ActionProtocol]"
    exit: "str | ActionProtocol | Sequence[str] | Sequence[ActionProtocol]"
    donedata: "ActionProtocol | None"


class StateKwargs(BaseStateKwargs, total=False):
    states: List[State]
    history: List[HistoryState]


class HistoryKwargs(TypedDict, total=False):
    name: str
    value: Any
    deep: bool


class HistoryDefinition(HistoryKwargs, total=False):
    on: TransitionsDict
    transitions: TransitionsList


class StateDefinition(BaseStateKwargs, total=False):
    states: Dict[str, "StateDefinition"]
    history: Dict[str, "HistoryDefinition"]
    on: TransitionsDict
    transitions: TransitionsList


def _parse_history(
    states: Mapping[str, "HistoryKwargs |HistoryDefinition"],
) -> Tuple[Dict[str, HistoryState], Dict[str, dict]]:
    states_instances: Dict[str, HistoryState] = {}
    events_definitions: Dict[str, dict] = {}
    for state_id, state_definition in states.items():
        state_definition = cast(HistoryDefinition, state_definition)
        transition_defs = state_definition.pop("on", {})
        transition_list = state_definition.pop("transitions", [])
        if transition_list:
            transition_defs[None] = transition_list

        if transition_defs:
            events_definitions[state_id] = transition_defs

        state_definition = cast(HistoryKwargs, state_definition)
        states_instances[state_id] = HistoryState(**state_definition)

    return (states_instances, events_definitions)


def _parse_states(
    states: Mapping[str, "BaseStateKwargs | StateDefinition"],
) -> Tuple[Dict[str, State], Dict[str, dict]]:
    states_instances: Dict[str, State] = {}
    events_definitions: Dict[str, dict] = {}

    for state_id, state_definition in states.items():
        # Process nested states. Replaces `states` as a definition by a list of `State` instances.
        state_definition = cast(StateDefinition, state_definition)

        # pop the nested states, history and transitions definitions
        inner_states_defs: Dict[str, StateDefinition] = state_definition.pop("states", {})
        inner_history_defs: Dict[str, HistoryDefinition] = state_definition.pop("history", {})
        transition_defs = state_definition.pop("on", {})
        transition_list = state_definition.pop("transitions", [])
        if transition_list:
            transition_defs[None] = transition_list

        if inner_states_defs:
            inner_states, inner_events = _parse_states(inner_states_defs)

            top_level_states = [
                state._set_id(state_id)
                for state_id, state in inner_states.items()
                if not state.parent
            ]
            state_definition["states"] = top_level_states  # type: ignore
            states_instances.update(inner_states)
            events_definitions.update(inner_events)

        if inner_history_defs:
            inner_history, inner_events = _parse_history(inner_history_defs)

            top_level_history = [
                state._set_id(state_id)
                for state_id, state in inner_history.items()
                if not state.parent
            ]
            state_definition["history"] = top_level_history  # type: ignore
            states_instances.update(inner_history)
            events_definitions.update(inner_events)

        if transition_defs:
            events_definitions[state_id] = transition_defs

        state_definition = cast(BaseStateKwargs, state_definition)
        states_instances[state_id] = State(**state_definition)

    return (states_instances, events_definitions)


def create_machine_class_from_definition(
    name: str, states: Mapping[str, "StateKwargs | StateDefinition"], **definition
) -> "type[StateChart]":  # noqa: C901
    """Create a StateChart class dynamically from a dictionary definition.

    Args:
        name: The class name for the generated state machine.
        states: A mapping of state IDs to state definitions. Each state definition
            can include ``initial``, ``final``, ``parallel``, ``name``, ``value``,
            ``enter``/``exit`` callbacks, ``donedata``, nested ``states``,
            ``history``, and transitions via ``on`` (event-triggered) or
            ``transitions`` (eventless).
        **definition: Additional keyword arguments passed to the metaclass
            (e.g., ``validate_disconnected_states=False``).

    Returns:
        A new StateChart subclass configured with the given states and transitions.

    Example:

    >>> machine = create_machine_class_from_definition(
    ...     "TrafficLightMachine",
    ...     **{
    ...         "states": {
    ...             "green": {"initial": True, "on": {"change": [{"target": "yellow"}]}},
    ...             "yellow": {"on": {"change": [{"target": "red"}]}},
    ...             "red": {"on": {"change": [{"target": "green"}]}},
    ...         },
    ...     }
    ... )

    """
    states_instances, events_definitions = _parse_states(states)

    events: Dict[str, TransitionList] = {}
    for state_id, state_events in events_definitions.items():
        for event_name, transitions_data in state_events.items():
            for transition_data in transitions_data:
                source = states_instances[state_id]

                target_state_id = transition_data["target"]
                transition_event_name = transition_data.get("event")
                if event_name is not None and transition_event_name is not None:
                    transition_event_name = f"{event_name} {transition_event_name}"
                elif event_name is not None:
                    transition_event_name = event_name

                transition_kwargs = {
                    "event": transition_event_name,
                    "internal": transition_data.get("internal"),
                    "initial": transition_data.get("initial"),
                    "cond": transition_data.get("cond"),
                    "unless": transition_data.get("unless"),
                    "on": transition_data.get("on"),
                    "before": transition_data.get("before"),
                    "after": transition_data.get("after"),
                }

                # Handle multi-target transitions (space-separated target IDs)
                if target_state_id and isinstance(target_state_id, str) and " " in target_state_id:
                    target_ids = target_state_id.split()
                    targets = [states_instances[tid] for tid in target_ids]
                    t = Transition(source, target=targets, **transition_kwargs)
                    source.transitions.add_transitions(t)
                    transition = TransitionList([t])
                else:
                    target = states_instances[target_state_id] if target_state_id else None
                    transition = source.to(target, **transition_kwargs)

                if event_name in events:
                    events[event_name] |= transition
                elif event_name is not None:
                    events[event_name] = transition

    top_level_states = {
        state_id: state for state_id, state in states_instances.items() if not state.parent
    }

    attrs_mapper = {**definition, **top_level_states, **events}
    return StateMachineMetaclass(name, (StateChart,), attrs_mapper)  # type: ignore[return-value]
