from typing import Dict

from ..factory import StateMachineMetaclass
from ..state import State
from ..statemachine import StateMachine
from ..transition_list import TransitionList


def create_machine_class_from_definition(name: str, definition: dict) -> StateMachine:
    """
    Creates a StateMachine class from a dictionary definition, using the StateMachineMetaclass.

    Example usage with a traffic light machine:

    >>> machine = create_machine_class_from_definition(
    ...     "TrafficLightMachine",
    ...     {
    ...         "states": {
    ...             "green": {"initial": True},
    ...             "yellow": {},
    ...             "red": {},
    ...         },
    ...         "events": {
    ...             "change": [
    ...                 {"from": "green", "to": "yellow"},
    ...                 {"from": "yellow", "to": "red"},
    ...                 {"from": "red", "to": "green"},
    ...             ]
    ...         },
    ...     }
    ... )

    """

    states_instances = {
        state_id: State(**state_kwargs)
        for state_id, state_kwargs in definition.pop("states").items()
    }

    events: Dict[str, TransitionList] = {}
    for event_name, transitions in definition.pop("events").items():
        for transition_data in transitions:
            source = states_instances[transition_data["from"]]
            target = states_instances[transition_data["to"]]

            transition = source.to(
                target,
                event=event_name,
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

    attrs_mapper = {**definition, **states_instances, **events}
    return StateMachineMetaclass(name, (StateMachine,), attrs_mapper)  # type: ignore[return-value]
