"""
Simple SCXML parser that converts SCXML documents to state machine definitions.
"""

import xml.etree.ElementTree as ET
from functools import partial
from typing import Any
from typing import Dict
from typing import List

from statemachine.statemachine import StateMachine


def send_event(machine: StateMachine, event_to_send: str) -> None:
    machine.send(event_to_send)


def assign(model, location, expr):
    pass


def strip_namespaces(tree):
    """Remove all namespaces from tags and attributes in place.

    Leaves only the local names in the subtree.
    """
    for el in tree.iter():
        tag = el.tag
        if tag and isinstance(tag, str) and tag[0] == "{":
            el.tag = tag.partition("}")[2]
        attrib = el.attrib
        if attrib:
            for name, value in list(attrib.items()):
                if name and isinstance(name, str) and name[0] == "{":
                    del attrib[name]
                    attrib[name.partition("}")[2]] = value


def parse_scxml(scxml_content: str) -> Dict[str, Any]:  # noqa: C901
    """
    Parse SCXML content and return a dictionary definition compatible with
    create_machine_class_from_definition.

    The returned dictionary has the format:
    {
        "states": {
            "state_id": {"initial": True},
            ...
        },
        "events": {
            "event_name": [
                {"from": "source_state", "to": "target_state"},
                ...
            ]
        }
    }
    """
    # Parse XML content
    root = ET.fromstring(scxml_content)
    strip_namespaces(root)

    # Find the scxml element (it might be the root or a child)
    scxml = root if "scxml" in root.tag else root.find(".//scxml")
    if scxml is None:
        raise ValueError("No scxml element found in document")

    # Get initial state from scxml element
    initial_state = scxml.get("initial")

    # Build states dictionary
    states = {}
    events: Dict[str, List[Dict[str, str]]] = {}

    def _parse_state(state_elem, final=False):  # noqa: C901
        state_id = state_elem.get("id")
        if not state_id:
            raise ValueError("All states must have an id")

        # Mark as initial if specified
        states[state_id] = {"initial": state_id == initial_state, "final": final}

        # Process transitions
        for trans_elem in state_elem.findall("transition"):
            event = trans_elem.get("event") or None
            target = trans_elem.get("target")

            if target:
                if event not in events:
                    events[event] = []

                if target not in states:
                    states[target] = {}

                events[event].append(
                    {
                        "from": state_id,
                        "to": target,
                    }
                )

        for onentry_elem in state_elem.findall("onentry"):
            for raise_elem in onentry_elem.findall("raise"):
                event = raise_elem.get("event")
                if event:
                    state = states[state_id]
                    if "enter" not in state:
                        state["enter"] = []
                    state["enter"].append(partial(send_event, event_to_send=event))

    # First pass: collect all states and mark initial
    for state_elem in scxml.findall(".//state"):
        _parse_state(state_elem)

    # Second pass: collect final states
    for state_elem in scxml.findall(".//final"):
        _parse_state(state_elem, final=True)

    # If no initial state was specified, mark the first state as initial
    if not initial_state and states:
        first_state = next(iter(states))
        states[first_state]["initial"] = True

    return {
        "states": states,
        "events": events,
    }
