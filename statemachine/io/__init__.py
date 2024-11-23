from typing import Dict

from ..factory import StateMachineMetaclass
from ..state import State
from ..statemachine import StateMachine
from ..transition_list import TransitionList


def create_machine_class_from_definition(name: str, definition: dict) -> StateMachine:  # noqa: C901
    """
    Creates a StateMachine class from a dictionary definition, using the StateMachineMetaclass.

    Example usage with a traffic light machine:

    >>> machine = create_machine_class_from_definition(
    ...     "TrafficLightMachine",
    ...     {
    ...         "states": {
    ...             "green": {"initial": True, "on": {"change": {"target": "yellow"}}},
    ...             "yellow": {"on": {"change": {"target": "red"}}},
    ...             "red": {"on": {"change": {"target": "green"}}},
    ...         },
    ...     }
    ... )

    """
    states_instances: Dict[str, State] = {}
    events_definitions: Dict[str, dict] = {}

    for state_id, state_kwargs in definition.pop("states").items():
        on_events = state_kwargs.pop("on", {})
        if on_events:
            events_definitions[state_id] = on_events

        states_instances[state_id] = State(**state_kwargs)

    events: Dict[str, TransitionList] = {}
    for state_id, state_events in events_definitions.items():
        for event_name, transition_data in state_events.items():
            source = states_instances[state_id]

            target = states_instances[transition_data["target"]]

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
