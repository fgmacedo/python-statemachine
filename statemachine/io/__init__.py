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
from ..state import State
from ..statemachine import StateMachine
from ..transition_list import TransitionList


class ActionProtocol(Protocol):
    def __call__(self, *args, **kwargs) -> Any: ...


class TransitionDict(TypedDict, total=False):
    target: str
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


class BaseStateKwargs(TypedDict, total=False):
    name: str
    value: Any
    initial: bool
    final: bool
    parallel: bool
    enter: "str | ActionProtocol | Sequence[str] | Sequence[ActionProtocol]"
    exit: "str | ActionProtocol | Sequence[str] | Sequence[ActionProtocol]"


class StateKwargs(BaseStateKwargs, total=False):
    states: List[State]


class StateDefinition(BaseStateKwargs, total=False):
    states: Dict[str, "StateDefinition"]
    on: TransitionsDict


def _parse_states(
    states: Mapping[str, "BaseStateKwargs | StateDefinition"],
) -> Tuple[Dict[str, State], Dict[str, dict]]:
    states_instances: Dict[str, State] = {}
    events_definitions: Dict[str, dict] = {}

    for state_id, state_kwargs in states.items():
        # Process nested states. Replaces `states` as a definition by a list of `State` instances.
        inner_states_definitions: Dict[str, StateDefinition] = cast(
            StateDefinition, state_kwargs
        ).pop("states", {})
        if inner_states_definitions:
            inner_states, inner_events = _parse_states(inner_states_definitions)

            top_level_states = [
                state._set_id(state_id)
                for state_id, state in inner_states.items()
                if not state.parent
            ]
            state_kwargs["states"] = top_level_states  # type: ignore
            states_instances.update(inner_states)
            events_definitions.update(inner_events)
        transition_definitions = cast(StateDefinition, state_kwargs).pop("on", {})
        if transition_definitions:
            events_definitions[state_id] = transition_definitions

        states_instances[state_id] = State(**state_kwargs)

    return (states_instances, events_definitions)


def create_machine_class_from_definition(
    name: str, states: Mapping[str, "StateKwargs | StateDefinition"], **definition
) -> StateMachine:  # noqa: C901
    """
    Creates a StateMachine class from a dictionary definition, using the StateMachineMetaclass.

    Example usage with a traffic light machine:

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

                target = states_instances[transition_data["target"]]

                # TODO: Join `trantion_data.event` with `event_name`
                transition = source.to(
                    target,
                    event=event_name,
                    internal=transition_data.get("internal"),
                    initial=transition_data.get("initial"),
                    cond=transition_data.get("cond"),
                    unless=transition_data.get("unless"),
                    on=transition_data.get("on"),
                    before=transition_data.get("before"),
                    after=transition_data.get("after"),
                )

                if event_name in events:
                    events[event_name] |= transition
                elif event_name is not None:
                    events[event_name] = transition

    top_level_states = {
        state_id: state for state_id, state in states_instances.items() if not state.parent
    }

    attrs_mapper = {**definition, **top_level_states, **events}
    return StateMachineMetaclass(name, (StateMachine,), attrs_mapper)  # type: ignore[return-value]
