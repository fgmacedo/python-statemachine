import re
import xml.etree.ElementTree as ET
from typing import Iterable
from typing import Set
from urllib.parse import urlparse

from .schema import Action
from .schema import AssignAction
from .schema import CancelAction
from .schema import DataItem
from .schema import DataModel
from .schema import ExecutableContent
from .schema import ForeachAction
from .schema import IfAction
from .schema import IfBranch
from .schema import LogAction
from .schema import Param
from .schema import RaiseAction
from .schema import ScriptAction
from .schema import SendAction
from .schema import State
from .schema import StateMachineDefinition
from .schema import Transition


def strip_namespaces(tree: ET.Element):
    """Remove all namespaces from tags and attributes in place."""
    for el in tree.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
        attrib = el.attrib
        for name in list(attrib.keys()):
            if "}" in name:
                new_name = name.split("}", 1)[1]
                attrib[new_name] = attrib.pop(name)


def visit_states(states: Iterable[State], parents: list[State]):
    for state in states:
        yield state, parents
        if state.states:
            yield from visit_states(state.states.values(), parents + [state])


def _parse_initial(initial_content: "str | None") -> Set[str]:
    if initial_content is None:
        return set()
    return set(initial_content.split())


def parse_scxml(scxml_content: str) -> StateMachineDefinition:  # noqa: C901
    root = ET.fromstring(scxml_content)
    strip_namespaces(root)

    scxml = root if root.tag == "scxml" else root.find(".//scxml")
    if scxml is None:
        raise ValueError("No scxml element found in document")

    initial_state = _parse_initial(scxml.get("initial"))
    name = scxml.get("name")

    definition = StateMachineDefinition(name=name, initial_states=initial_state)

    # Parse datamodel
    datamodel = parse_datamodel(scxml)
    if datamodel:
        definition.datamodel = datamodel

    # Parse states
    for state_elem in scxml:
        if state_elem.tag == "state":
            state = parse_state(state_elem, definition.initial_states)
            definition.states[state.id] = state
        elif state_elem.tag == "final":
            state = parse_state(state_elem, definition.initial_states, is_final=True)
            definition.states[state.id] = state
        elif state_elem.tag == "parallel":
            state = parse_state(state_elem, definition.initial_states, is_parallel=True)
            definition.states[state.id] = state

    # If no initial state was specified, pick the first state
    if not definition.initial_states and definition.states:
        definition.initial_states = {next(key for key in definition.states.keys())}
        for s in definition.initial_states:
            definition.states[s].initial = True

    # If the initial states definition does not contain any first level state,
    # we find the first level states that are ancestor of the initial states
    # and also set them as the initial states
    if not set(definition.states.keys()) & definition.initial_states:
        not_found = set(definition.initial_states)
        for state, parents in visit_states(definition.states.values(), []):
            if state.id in definition.initial_states:
                not_found.remove(state.id)
                for parent in parents:
                    parent.initial = True
                    definition.initial_states.add(parent.id)
            if not not_found:
                break

    return definition


def parse_datamodel(root: ET.Element) -> "DataModel | None":
    data_model = DataModel()

    for datamodel_elem in root.findall(".//datamodel"):
        for data_elem in datamodel_elem.findall("data"):
            content = data_elem.text and re.sub(r"\s+", " ", data_elem.text).strip() or None
            src = data_elem.attrib.get("src")
            src_parsed = urlparse(src) if src else None
            if src_parsed and src_parsed.scheme == "file" and content is None:
                with open(src_parsed.path) as f:
                    content = f.read()

            data_model.data.append(
                DataItem(
                    id=data_elem.attrib["id"],
                    src=src_parsed,
                    expr=data_elem.attrib.get("expr"),
                    content=content,
                )
            )

    # Parse <script> elements outside of <datamodel>
    for script_elem in root.findall("script"):
        script_content = ScriptAction(
            content=script_elem.text.strip() if script_elem.text else "",
        )
        data_model.scripts.append(script_content)

    return data_model if data_model.data or data_model.scripts else None


def parse_state(
    state_elem: ET.Element,
    initial_states: Set[str],
    is_final: bool = False,
    is_parallel: bool = False,
) -> State:
    state_id = state_elem.get("id")
    if not state_id:
        raise ValueError("State must have an 'id' attribute")

    initial = state_id in initial_states
    state = State(id=state_id, initial=initial, final=is_final, parallel=is_parallel)

    # Parse onentry actions
    for onentry_elem in state_elem.findall("onentry"):
        content = parse_executable_content(onentry_elem)
        state.onentry.append(content)

    # Parse onexit actions
    for onexit_elem in state_elem.findall("onexit"):
        content = parse_executable_content(onexit_elem)
        state.onexit.append(content)

    # Parse transitions
    for trans_elem in state_elem.findall("transition"):
        transition = parse_transition(trans_elem)
        state.transitions.append(transition)

    # Parse child states
    initial_states |= _parse_initial(state_elem.get("initial"))
    initial_elem = state_elem.find("initial")
    if initial_elem is not None:
        for trans_elem in initial_elem.findall("transition"):
            transition = parse_transition(trans_elem, initial=True)
            state.transitions.append(transition)
            initial_states |= _parse_initial(trans_elem.get("target"))

    for child_state_elem in state_elem.findall("state"):
        child_state = parse_state(child_state_elem, initial_states=initial_states)
        state.states[child_state.id] = child_state
    for child_state_elem in state_elem.findall("final"):
        child_state = parse_state(child_state_elem, initial_states=initial_states, is_final=True)
        state.states[child_state.id] = child_state
    for child_state_elem in state_elem.findall("parallel"):
        child_state = parse_state(
            child_state_elem, initial_states=initial_states, is_parallel=True
        )
        state.states[child_state.id] = child_state

    return state


def parse_transition(trans_elem: ET.Element, initial: bool = False) -> Transition:
    target = trans_elem.get("target")

    event = trans_elem.get("event")
    cond = trans_elem.get("cond")
    internal = trans_elem.get("type") == "internal"

    executable_content = parse_executable_content(trans_elem)

    return Transition(
        target=target,
        internal=internal,
        initial=initial,
        event=event,
        cond=cond,
        on=executable_content,
    )


def parse_executable_content(element: ET.Element) -> ExecutableContent:
    """Parses the children as <executable> content XML into a list of Action instances."""
    actions = []
    for child in element:
        action = parse_element(child)
        if action:
            actions.append(action)
    return ExecutableContent(actions=actions)


def parse_element(element: ET.Element) -> Action:
    tag = element.tag
    if tag == "raise":
        return parse_raise(element)
    elif tag == "assign":
        return parse_assign(element)
    elif tag == "log":
        return parse_log(element)
    elif tag == "if":
        return parse_if(element)
    elif tag == "send":
        return parse_send(element)
    elif tag == "script":
        return parse_script(element)
    elif tag == "foreach":
        return parse_foreach(element)
    elif tag == "cancel":
        return parse_cancel(element)

    raise ValueError(f"Unknown tag: {tag}")


def parse_raise(element: ET.Element) -> RaiseAction:
    event = element.attrib["event"]
    return RaiseAction(event=event)


def parse_assign(element: ET.Element) -> AssignAction:
    location = element.attrib["location"]
    expr = element.attrib["expr"]
    return AssignAction(location=location, expr=expr)


def parse_log(element: ET.Element) -> LogAction:
    label = element.attrib.get("label")
    expr = element.attrib.get("expr")
    return LogAction(label=label, expr=expr)


def parse_if(element: ET.Element) -> IfAction:
    current_branch = IfBranch(cond=element.attrib["cond"])
    branches = [current_branch]
    for child in element:
        tag = child.tag
        if tag in ("elseif", "else"):
            current_branch = IfBranch(cond=child.attrib.get("cond"))
            branches.append(current_branch)
        else:
            # Add the action to the current branch
            action = parse_element(child)
            current_branch.append(action)

    return IfAction(branches=branches)


def parse_foreach(element: ET.Element) -> ForeachAction:
    array = element.attrib["array"]
    item = element.attrib["item"]
    index = element.attrib.get("index")
    content = parse_executable_content(element)
    return ForeachAction(array=array, item=item, index=index, content=content)


def parse_send(element: ET.Element) -> SendAction:
    """
    Parses the <send> element into SendAction.

    Attributes:
    - `event`: The name of the event to send (required).
    - `target`: The target to which the event is sent (optional).
    - `type`: The type of the event (optional).
    - `id`: A unique identifier for this send action (optional).
    - `delay`: The delay before sending the event (optional).
    - `namelist`: A space-separated list of data model variables to include in the event (optional)
    - `params`: A dictionary of parameters to include in the event (optional).
    - `content`: Content to include in the event (optional).
    """

    event = element.attrib.get("event")
    eventexpr = element.attrib.get("eventexpr")

    if not (event or eventexpr):
        raise ValueError("<send> must have an 'event' or `eventexpr` attribute")

    target = element.attrib.get("target")
    type_attr = element.attrib.get("type")
    id_attr = element.attrib.get("id")
    idlocation = element.attrib.get("idlocation")
    delay = element.attrib.get("delay")
    delayexpr = element.attrib.get("delayexpr")
    namelist = element.attrib.get("namelist")

    params = []
    content = None
    for child in element:
        if child.tag == "param":
            name = child.attrib["name"]
            expr = child.attrib.get("expr")
            location = child.attrib.get("location")
            if not (expr or location):
                raise ValueError("Must specify ")
            params.append(
                Param(
                    name=name,
                    expr=expr,
                    location=location,
                )
            )
        elif child.tag == "content":
            content = re.sub(r"\s+", " ", child.text).strip() if child.text else None

    return SendAction(
        event=event,
        eventexpr=eventexpr,
        target=target,
        type=type_attr,
        id=id_attr,
        idlocation=idlocation,
        delay=delay,
        delayexpr=delayexpr,
        namelist=namelist,
        params=params,
        content=content,
    )


def parse_cancel(element: ET.Element) -> CancelAction:
    sendid = element.attrib.get("sendid")
    sendidexpr = element.attrib.get("sendidexpr")
    return CancelAction(sendid=sendid, sendidexpr=sendidexpr)


def parse_script(element: ET.Element) -> ScriptAction:
    content = element.text.strip() if element.text else ""
    return ScriptAction(content=content)
