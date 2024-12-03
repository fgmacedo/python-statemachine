"""
Simple SCXML parser that converts SCXML documents to state machine definitions.
"""

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from uuid import uuid4

from statemachine.event import Event
from statemachine.io import create_machine_class_from_definition

from ..model import Model
from ..statemachine import StateMachine


@dataclass
class _Data:
    kwargs: dict

    def __getattr__(self, name):
        return self.kwargs.get(name, None)

    def get(self, name, default=None):
        return self.kwargs.get(name, default)


class EventDataWrapper:
    origin: str = ""
    origintype: str = "http://www.w3.org/TR/scxml/#SCXMLEventProcessor"
    """The origintype of the :ref:`Event` as specified by the SCXML namespace."""

    def __init__(self, event_data):
        self.event_data = event_data

    def __getattr__(self, name):
        return getattr(self.event_data, name)

    @property
    def data(self):
        "Property used by the SCXML namespace"
        if self.trigger_data.kwargs:
            return _Data(self.trigger_data.kwargs)
        elif self.trigger_data.args and len(self.trigger_data.args) == 1:
            return self.trigger_data.args[0]
        else:
            return self.trigger_data.args


def _eval(expr: str, **kwargs) -> Any:
    if "machine" in kwargs:
        kwargs.update(kwargs["machine"].model.__dict__)
    if "event_data" in kwargs:
        kwargs["_event"] = EventDataWrapper(kwargs["event_data"])

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
    elif tag == "script":
        return parse_script(element)
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
    label = element.attrib.get("label")
    expr = element.attrib["expr"]

    def raise_log(*args, **kwargs):
        machine = kwargs["machine"]
        kwargs.update(machine.model.__dict__)
        value = _eval(expr, **kwargs)
        if label:
            print(f"{label}: {value!r}")
        else:
            print(f"{value!r}")

    return raise_log


def parse_assign(element):
    """Parses the <assign> element into a callable."""
    location = element.attrib.get("location")
    expr = element.attrib["expr"]

    def assign_action(*args, **kwargs):
        machine = kwargs["machine"]
        value = _eval(expr, **kwargs)

        *path, attr = location.split(".")
        obj = machine.model
        for p in path:
            obj = getattr(obj, p)

        if not attr.isidentifier():
            raise ValueError(
                f"<assign> 'location' must be a valid Python attribute name, got: {location}"
            )
        setattr(obj, attr, value)

    return assign_action


def parse_script(element):
    """
    Parses the <script> element, executes its content, and assigns
    the resulting variables to the statemachine.model.

    Args:
        element: The XML <script> element containing the code to execute.

    Returns:
        A callable that executes the script within the state machine's context.
    """
    script_content = element.text.strip()

    def script_action(*args, **kwargs):
        machine = kwargs.get("machine")

        local_vars = {
            **machine.model.__dict__,
        }
        exec(script_content, {}, local_vars)

        # Assign the resulting variables to the state machine's model
        for var_name, value in local_vars.items():
            setattr(machine.model, var_name, value)

    return script_action


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

        try:
            # Evaluate the array expression to get the iterable
            array = _eval(array_expr, **kwargs)
        except Exception as e:
            raise ValueError(f"Error evaluating <foreach> 'array' expression: {e}") from e

        if not item_var.isidentifier():
            raise ValueError(
                f"<foreach> 'item' must be a valid Python attribute name, got: {item_var}"
            )
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


def parse_cond(cond, processor=None):
    """Parses the <cond> element into a callable."""
    cond = _normalize_cond(cond)
    if cond is None:
        return None

    def cond_action(*args, **kwargs):
        if processor:
            kwargs["_ioprocessors"] = processor.wrap(**kwargs)

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


def parse_datamodel(root):
    """
    Parses the <datamodel> element into a callable that initializes the state machine model.

    Each <data> element defines a variable with an `id` and an optional `expr`.
    """
    data_elements = []
    for element in root.iter():
        if element.tag == "scxml":
            continue
        if element.tag == "datamodel":
            data_elements.extend([parse_data(child) for child in element])

    scripts = root.findall("./script")
    if scripts:
        data_elements.extend([parse_script(child) for child in scripts])

    if not data_elements:
        return None

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
        self.model = model
        for data_action in data_elements:
            data_action(machine=self)

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
    content = element.text and re.sub(r"\s+", " ", element.text).strip() or None

    def data_initializer(**kwargs):
        # Evaluate the expression if provided, or set to None
        machine = kwargs["machine"]
        if expr:
            value = _eval(expr, **kwargs)
        else:
            try:
                value = _eval(content, **kwargs)
            except Exception:
                value = content
        setattr(machine.model, data_id, value)

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
            try:
                content = (_eval(child.text),)
            except (NameError, IndentationError, SyntaxError, TypeError):
                content = (re.sub(r"\s+", " ", child.text).strip(),)

    def send_action(*args, **kwargs):
        machine = kwargs["machine"]
        context = {**machine.model.__dict__}

        # Evaluate expressions
        event = event_attr or _eval(event_expr, **kwargs)
        _target = _eval(target_expr, **kwargs) if target_expr else None
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
            delay = ParseTime.time_in_ms(_eval(delay_expr_expanded, **kwargs))
        else:
            delay = 0

        params_values = {}
        if namelist_expr:
            for name in namelist_expr.split():
                if name in context:
                    params_values[name] = _eval(name, **kwargs)

        for name, expr in params.items():
            params_values[name] = _eval(expr, **kwargs)

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


def parse_scxml(  # noqa: C901
    scxml_content: str, processor: "SCXMLProcessor", location: str
):
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
            cond = parse_cond(trans_elem.get("cond"), processor=processor)
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
    datamodel = parse_datamodel(scxml)
    if datamodel is not None:
        extra_data["__init__"] = datamodel

    # If no initial state was specified, mark the first state as initial
    if not initial_state and states:
        first_state = next(iter(states))
        states[first_state]["initial"] = True

    processor._add(location, {"states": states, **extra_data})


class SCXMLProcessor:
    def __init__(self):
        self.scs = {}
        self.sessions = {}
        self._ioprocessors = {
            "http://www.w3.org/TR/scxml/#SCXMLEventProcessor": self,
            "scxml": self,
        }

    def parse_scxml_file(self, path: Path):
        scxml_content = path.read_text()
        return self.parse_scxml(path.stem, scxml_content)

    def parse_scxml(self, sm_name: str, scxml_content: str):
        parse_scxml(scxml_content, self, location=sm_name)

    def _add(self, location: str, definition: Dict[str, Any]):
        try:
            sc_class = create_machine_class_from_definition(location, **definition)
            self.scs[location] = sc_class
            return sc_class
        except Exception as e:
            raise Exception(
                f"Failed to create state machine class: {e} from definition: {definition}"
            ) from e

    def start(self, **kwargs):
        self.root_cls = next(iter(self.scs.values()))
        self.root = self.root_cls(**kwargs)
        self.sessions[self.root.name] = self.root
        return self.root

    def wrap(self, **kwargs):
        return IOProcessor(self, **kwargs)


class IOProcessor:
    def __init__(self, processor: "SCXMLProcessor", **kwargs):
        self.scxml_processor = processor
        self.machine = kwargs["machine"]

    def __getitem__(self, name: str):
        return self

    @property
    def location(self):
        return self.machine.name
