from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Mapping
from typing import TypedDict
from typing import cast

from ..factory import StateMachineMetaclass
from ..state import State
from ..statemachine import StateMachine
from ..transition_list import TransitionList

CallbacksType = str | Callable | List[str] | List[Callable]


class TransitionDict(TypedDict, total=False):
    target: str
    event: str
    internal: bool
    validators: bool
    cond: CallbacksType
    unless: CallbacksType
    on: CallbacksType
    before: CallbacksType
    after: CallbacksType


class StateDict(TypedDict, total=False):
    name: str
    value: Any
    initial: bool
    final: bool
    enter: CallbacksType
    exit: CallbacksType


class StateWithTransitionsDict(StateDict, total=False):
    on: Dict[str, List[TransitionDict]]


StateOptions = StateDict | StateWithTransitionsDict


def create_machine_class_from_definition(
    name: str, states: Mapping[str, StateOptions], **definition
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
    states_instances: Dict[str, State] = {}
    events_definitions: Dict[str, dict] = {}

    for state_id, state_kwargs in states.items():
        transition_definitions = cast(StateWithTransitionsDict, state_kwargs).pop("on", {})
        if transition_definitions:
            events_definitions[state_id] = transition_definitions

        states_instances[state_id] = State(**state_kwargs)

    events: Dict[str, TransitionList] = {}
    for state_id, state_events in events_definitions.items():
        for event_name, transitions_data in state_events.items():
            for trantion_data in transitions_data:
                source = states_instances[state_id]

                target = states_instances[trantion_data["target"]]

                transition = source.to(
                    target,
                    event=event_name,
                    cond=trantion_data.get("cond"),
                    unless=trantion_data.get("unless"),
                    on=trantion_data.get("on"),
                    before=trantion_data.get("before"),
                    after=trantion_data.get("after"),
                )

                if event_name in events:
                    events[event_name] |= transition
                elif event_name is not None:
                    events[event_name] = transition

    attrs_mapper = {**definition, **states_instances, **events}
    return StateMachineMetaclass(name, (StateMachine,), attrs_mapper)  # type: ignore[return-value]
