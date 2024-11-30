"""
Simple SCXML parser that converts SCXML documents to state machine definitions.
"""

import html
import re
import xml.etree.ElementTree as ET
from typing import Any
from typing import Dict
from typing import List
from uuid import uuid4

from statemachine.event import Event

from ..model import Model
from ..statemachine import StateMachine


def _eval(expr: str, **kwargs) -> Any:
    if "machine" in kwargs:
        kwargs.update(kwargs["machine"].model.__dict__)
    if "event_data" in kwargs:
        kwargs["_event"] = kwargs["event_data"]

    return eval(expr, {}, kwargs)


def parse_executable_content(element):
    """Parses the children as <executable> content XML into a callable."""
    actions = [parse_element(child) for child in element]

    def execute_block(*args, **kwargs):
        machine = kwargs["machine"]
        try:
            for action in actions:
                action(*args, **kwargs)

            machine._processing_loop()
        except Exception as e:
            machine.send("error.execution", error=e)

    if not actions:
        return None
    return execute_block


def parse_element(element):
    """Parses an individual XML element into a callable."""
    tag = element.tag
    if tag == "raise":
        return parse_raise(element)
    elif tag == "assign":
        return parse_assign(element)
    elif tag == "foreach":
        return parse_foreach(element)
    elif tag == "log":
        return parse_log(element)
    elif tag == "if":
        return parse_if(element)
    elif tag == "send":
        return parse_send(element)
    elif tag == "cancel":
        return parse_cancel(element)
    else:
        raise ValueError(f"Unknown tag: {tag}")


def parse_raise(element):
    """Parses the <raise> element into a callable."""
    event = element.attrib["event"]

    def raise_action(*args, **kwargs):
        machine = kwargs["machine"]
        machine.send(event)

    return raise_action


def parse_cancel(element):
    """Parses the <cancel> element into a callable."""
    sendid = element.attrib.get("sendid")
    sendidexpr = element.attrib.get("sendidexpr")

    def cancel(*args, **kwargs):
        if sendid and sendidexpr:
            raise ValueError("<cancel> cannot have both a 'sendid' and 'sendidexpr' attribute")
        elif sendid:
            send_id = sendid
        elif sendidexpr:
            send_id = _eval(sendidexpr, **kwargs)
        else:
            raise ValueError("<cancel> must have either a 'sendid' or 'sendidexpr' attribute")
        machine = kwargs["machine"]
        machine.cancel_event(send_id)

    return cancel


def parse_log(element):
    """Parses the <log> element into a callable."""
    label = element.attrib["label"]
    expr = element.attrib["expr"]

    def raise_log(*args, **kwargs):
        machine = kwargs["machine"]
        kwargs.update(machine.model.__dict__)
        value = _eval(expr, **kwargs)
        print(f"{label}: {value!r}")

    return raise_log


def parse_assign(element):
    """Parses the <assign> element into a callable."""
    location = element.attrib["location"]
    expr = element.attrib["expr"]

    def assign_action(*args, **kwargs):
        machine = kwargs["machine"]
        value = _eval(expr, **kwargs)
        setattr(machine.model, location, value)

    return assign_action


def parse_foreach(element):  # noqa: C901
    """
    Parses the <foreach> element into a callable.

    - `array`: The iterable collection (required).
    - `item`: The variable name for the current item (required).
    - `index`: The variable name for the current index (optional).
    - Child elements are executed for each iteration.
    """
    array_expr = element.attrib.get("array")
    if not array_expr:
        raise ValueError("<foreach> must have an 'array' attribute")

    item_var = element.attrib.get("item")
    if not item_var:
        raise ValueError("<foreach> must have an 'item' attribute")

    index_var = element.attrib.get("index")
    child_actions = [parse_element(child) for child in element]

    def foreach_action(*args, **kwargs):  # noqa: C901
        machine = kwargs["machine"]
        context = {**machine.model.__dict__}  # Shallow copy of the model's attributes

        try:
            # Evaluate the array expression to get the iterable
            array = eval(array_expr, {}, context)
            if not hasattr(array, "__iter__"):
                raise ValueError(
                    f"<foreach> 'array' must evaluate to an iterable, got: {type(array).__name__}"
                )
        except Exception as e:
            raise ValueError(f"Error evaluating <foreach> 'array' expression: {e}") from e

        if not item_var.isidentifier():
            raise ValueError(
                f"<foreach> 'item' must be a valid Python attribute name, got: {item_var}"
            )
        # Iterate over the array
        for index, item in enumerate(array):
            # Assign the item and optionally the index
            setattr(machine.model, item_var, item)
            if index_var:
                setattr(machine.model, index_var, index)

            # Execute child actions
            for action in child_actions:
                action(*args, **kwargs)

    return foreach_action


def _normalize_cond(cond: "str | None") -> "str | None":
    """
    Normalizes a JavaScript-like condition string to be compatible with Python's eval.

    - Replaces `true` with `True`.
    - Replaces `false` with `False`.
    - Replaces `null` with `None`.
    - Ensures equality operators `===` and `!==` are converted to Python's `==` and `!=`.
    - Handles logical operators `&&` and `||` converting them to `and` and `or`.
    """
    if cond is None:
        return None

    # Decode HTML entities, to allow XML syntax like `Var1&lt;Var2`
    cond = html.unescape(cond)

    replacements = {
        "true": "True",
        "false": "False",
        "null": "None",
        "===": "==",
        "!==": "!=",
        "&&": "and",
        "||": "or",
    }

    # Use regex to replace each JavaScript-like token with its Python equivalent
    pattern = re.compile(r"\b(?:true|false|null)\b|===|!==|&&|\|\|")
    return pattern.sub(lambda match: replacements[match.group(0)], cond)


def parse_cond(cond):
    """Parses the <cond> element into a callable."""
    cond = _normalize_cond(cond)
    if cond is None:
        return None

    def cond_action(*args, **kwargs):
        return _eval(cond, **kwargs)

    cond_action.cond = cond

    return cond_action


def parse_if(element):  # noqa: C901
    """Parses the <if> element into a callable."""
    branches = []
    else_branch = []

    current_cond = parse_cond(element.attrib.get("cond"))
    current_actions = []

    for child in element:
        tag = child.tag
        if tag in ("elseif", "else"):
            # Save the current branch before starting a new one
            if current_cond is not None:
                branches.append((current_cond, current_actions))

            # Update for the new branch
            if tag == "elseif":
                current_cond = parse_cond(child.attrib.get("cond"))
                current_actions = []
            elif tag == "else":
                current_cond = None
                current_actions = else_branch  # Start collecting actions for else
        else:
            # Add the action to the current branch
            current_actions.append(parse_element(child))

    # Add the last branch if needed
    if current_cond is not None:
        branches.append((current_cond, current_actions))
    else:
        else_branch = current_actions

    def if_action(*args, **kwargs):
        # Evaluate each branch in order
        for cond, actions in branches:
            if cond(*args, **kwargs):
                for action in actions:
                    action(*args, **kwargs)
                return
        # Execute the else branch if no condition matches
        for action in else_branch:
            action(*args, **kwargs)

    return if_action


def parse_datamodel(element):
    """
    Parses the <datamodel> element into a callable that initializes the state machine model.

    Each <data> element defines a variable with an `id` and an optional `expr`.
    """
    data_elements = [parse_data(child) for child in element]

    def __init__(
        self,
        model: Any = None,
        state_field: str = "state",
        start_value: Any = None,
        rtc: bool = True,
        allow_event_without_transition: bool = True,
        listeners: "List[object] | None" = None,
    ):
        model = model if model else Model()
        for data_action in data_elements:
            data_action(model)

        StateMachine.__init__(
            self,
            model,
            state_field=state_field,
            start_value=start_value,
            rtc=rtc,
            allow_event_without_transition=allow_event_without_transition,
            listeners=listeners,
        )

    return __init__


def parse_data(element):
    """
    Parses a single <data> element into a callable.

    - `id` is the variable name.
    - `expr` is the initial value expression (optional).
    """
    data_id = element.attrib["id"]
    expr = element.attrib.get("expr")
    if not expr:
        expr = element.text and element.text.strip()

    def data_initializer(model):
        # Evaluate the expression if provided, or set to None
        context = model.__dict__
        value = eval(expr, {}, context) if expr else None
        setattr(model, data_id, value)

    return data_initializer


class ParseTime:
    pattern = re.compile(r"(\d+)?(\.\d+)?(s|ms)")

    @classmethod
    def replace(cls, expr: str) -> str:
        def rep(match):
            return str(cls.time_in_ms(match.group(0)))

        return cls.pattern.sub(rep, expr)

    @classmethod
    def time_in_ms(cls, expr: str) -> float:
        """
        Convert a CSS2 time expression to milliseconds.

        Args:
            time (str): A string representing the time, e.g., '1.5s' or '150ms'.

        Returns:
            float: The time in milliseconds.

        Raises:
            ValueError: If the input is not a valid CSS2 time expression.
        """
        if expr.endswith("ms"):
            try:
                return float(expr[:-2])
            except ValueError as e:
                raise ValueError(f"Invalid time value: {expr}") from e
        elif expr.endswith("s"):
            try:
                return float(expr[:-1]) * 1000
            except ValueError as e:
                raise ValueError(f"Invalid time value: {expr}") from e
        else:
            try:
                return float(expr)
            except ValueError as e:
                raise ValueError(f"Invalid time unit in: {expr}") from e


def parse_send(element):  # noqa: C901
    """
    Parses the <send> element into a callable that dispatches events.

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
    event_attr = element.attrib.get("event")
    event_expr = element.attrib.get("eventexpr")
    if not (event_attr or event_expr):
        raise ValueError("<send> must have an 'event' or `eventexpr` attribute")

    target_expr = element.attrib.get("target")
    type_attr = element.attrib.get("type")
    id_attr = element.attrib.get("id")
    idlocation = element.attrib.get("idlocation")
    delay_attr = element.attrib.get("delay")
    delay_expr = element.attrib.get("delayexpr")
    namelist_expr = element.attrib.get("namelist")

    # Parse <param> and <content> child elements
    params = {}
    content = ()
    for child in element:
        if child.tag == "param":
            name = child.attrib.get("name")
            expr = child.attrib.get("expr")
            if name and expr:
                params[name] = expr
        elif child.tag == "content":
            content = (_eval(child.text),)

    def send_action(*args, **kwargs):
        machine = kwargs["machine"]
        context = {**machine.model.__dict__}

        # Evaluate expressions
        event = event_attr or eval(event_expr, {}, context)
        _target = eval(target_expr, {}, context) if target_expr else None
        if type_attr and type_attr != "http://www.w3.org/TR/scxml/#SCXMLEventProcessor":
            raise ValueError(
                "Only 'http://www.w3.org/TR/scxml/#SCXMLEventProcessor' event type is supported"
            )

        if id_attr:
            send_id = id_attr
        else:
            send_id = uuid4().hex
            if idlocation:
                setattr(machine.model, idlocation, send_id)

        if delay_attr:
            delay = ParseTime.time_in_ms(delay_attr)
        elif delay_expr:
            delay_expr_expanded = ParseTime.replace(delay_expr)
            delay = ParseTime.time_in_ms(eval(delay_expr_expanded, {}, context))
        else:
            delay = 0

        params_values = {}
        if namelist_expr:
            for name in namelist_expr.split():
                if name in context:
                    params_values[name] = context[name]

        for name, expr in params.items():
            params_values[name] = eval(expr, {}, context)

        Event(id=event, name=event, delay=delay).put(
            *content,
            machine=machine,
            send_id=send_id,
            **params_values,
        )

    return send_action


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

    The returned dictionary has the format compatible with
    :ref:`create_machine_class_from_definition`.
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
            cond = parse_cond(trans_elem.get("cond"))
            content_action = parse_executable_content(trans_elem)

            if target:
                state = states[state_id]

                # This "on" represents the events handled by the state
                # there's also a possibility of "on" as an action
                if "on" not in state:
                    state["on"] = {}

                if event not in state["on"]:
                    state["on"][event] = []

                transitions = state["on"][event]

                transition = {"target": target}
                if cond:
                    transition["cond"] = cond

                if content_action:
                    transition["on"] = content_action

                transitions.append(transition)

                if target not in states:
                    states[target] = {}

        for onentry_elem in state_elem.findall("onentry"):
            entry_action = parse_executable_content(onentry_elem)
            state = states[state_id]
            if "enter" not in state:
                state["enter"] = []
            state["enter"].append(entry_action)

    # First pass: collect all states and mark initial
    for state_elem in scxml.findall(".//state"):
        _parse_state(state_elem)

    # Second pass: collect final states
    for state_elem in scxml.findall(".//final"):
        _parse_state(state_elem, final=True)

    extra_data = {}

    # To initialize the data model, we override the SM __init__ method
    datamodel = scxml.find("datamodel")
    if datamodel is not None:
        extra_data["__init__"] = parse_datamodel(datamodel)

    # If no initial state was specified, mark the first state as initial
    if not initial_state and states:
        first_state = next(iter(states))
        states[first_state]["initial"] = True

    return {"states": states, **extra_data}
