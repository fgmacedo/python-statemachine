import html
import logging
import re
from dataclasses import dataclass
from itertools import chain
from typing import Any
from typing import Callable
from uuid import uuid4

from ...event import BoundEvent
from ...event import Event
from ...event import _event_data_kwargs
from ...spec_parser import InState
from ...statemachine import StateChart
from .parser import Action
from .parser import AssignAction
from .parser import IfAction
from .parser import LogAction
from .parser import RaiseAction
from .parser import SendAction
from .schema import CancelAction
from .schema import DataItem
from .schema import DataModel
from .schema import DoneData
from .schema import ExecutableContent
from .schema import ForeachAction
from .schema import Param
from .schema import ScriptAction

logger = logging.getLogger(__name__)
protected_attrs = _event_data_kwargs | {"_sessionid", "_ioprocessors", "_name", "_event"}


class ParseTime:
    pattern = re.compile(r"(\d+)?(\.\d+)?(s|ms)")

    @classmethod
    def parse_delay(cls, delay: "str | None", delayexpr: "str | None", **kwargs):
        if delay:
            return cls.time_in_ms(delay)
        elif delayexpr:
            delay_expr_expanded = cls.replace(delayexpr)
            return cls.time_in_ms(_eval(delay_expr_expanded, **kwargs))

        return 0

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


@dataclass
class _Data:
    kwargs: dict

    def __getattr__(self, name):
        return self.kwargs.get(name, None)

    def get(self, name, default=None):
        return self.kwargs.get(name, default)


class OriginTypeSCXML(str):
    """The origintype of the :ref:`Event` as specified by the SCXML namespace."""

    def __eq__(self, other):
        return other == "http://www.w3.org/TR/scxml/#SCXMLEventProcessor" or other == "scxml"


class EventDataWrapper:
    origin: str = ""
    origintype: str = OriginTypeSCXML("scxml")
    """The origintype of the :ref:`Event` as specified by the SCXML namespace."""
    invokeid: str = ""
    """If this event is generated from an invoked child process, the SCXML Processor MUST set
    this field to the invoke id of the invocation that triggered the child process.
    Otherwise it MUST leave it blank.
    """

    def __init__(self, event_data=None, *, trigger_data=None):
        self.event_data = event_data
        if trigger_data is not None:
            self.trigger_data = trigger_data
        elif event_data is not None:
            self.trigger_data = event_data.trigger_data
        else:
            raise ValueError("Either event_data or trigger_data must be provided")

        td = self.trigger_data
        self.sendid = td.send_id
        self.invokeid = td.kwargs.get("_invokeid", "")
        if td.event is None or td.event.internal:
            if "error.execution" == td.event:
                self.type = "platform"
            else:
                self.type = "internal"
                self.origintype = ""
        else:
            self.type = "external"

    @classmethod
    def from_trigger_data(cls, trigger_data):
        """Create an EventDataWrapper directly from a TriggerData (no EventData needed)."""
        return cls(trigger_data=trigger_data)

    def __getattr__(self, name):
        if self.event_data is not None:
            return getattr(self.event_data, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __eq__(self, value):
        "This makes SCXML test 329 pass. It assumes that the event is the same instance"
        return isinstance(value, EventDataWrapper)

    @property
    def name(self):
        if self.event_data is not None:
            return self.event_data.event
        return str(self.trigger_data.event) if self.trigger_data.event else None

    @property
    def data(self):
        "Property used by the SCXML namespace"
        td = self.trigger_data
        if td.kwargs:
            return _Data(td.kwargs)
        elif td.args and len(td.args) == 1:
            return td.args[0]
        elif td.args:
            return td.args
        else:
            return None


def _eval(expr: str, **kwargs) -> Any:
    if "machine" in kwargs:
        kwargs.update(
            **{
                k: v
                for k, v in kwargs["machine"].model.__dict__.items()
                if k not in protected_attrs
            }
        )
        kwargs["In"] = InState(kwargs["machine"])
    return eval(expr, {}, kwargs)


class CallableAction:
    action: Any

    def __init__(self):
        self.__qualname__ = f"{self.__class__.__module__}.{self.__class__.__name__}"

    def __call__(self, *args, **kwargs):
        raise NotImplementedError

    def __str__(self):
        return f"{self.action}"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.action!r})"

    @property
    def __name__(self):
        return str(self)

    @property
    def __code__(self):
        return self.__call__.__code__


class Cond(CallableAction):
    """Evaluates a condition like a predicate and returns True or False."""

    @classmethod
    def create(cls, cond: "str | None", processor=None):
        cond = cls._normalize(cond)
        if cond is None:
            return None

        return cls(cond, processor)

    def __init__(self, cond: str, processor=None):
        super().__init__()
        self.action = cond
        self.processor = processor

    def __call__(self, *args, **kwargs):
        result = _eval(self.action, **kwargs)
        logger.debug("Cond %s -> %s", self.action, result)
        return result

    @staticmethod
    def _normalize(cond: "str | None") -> "str | None":
        """
        Normalizes a JavaScript-like condition string to be compatible with Python's eval.
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


def create_action_callable(action: Action) -> Callable:
    if isinstance(action, RaiseAction):
        return create_raise_action_callable(action)
    elif isinstance(action, AssignAction):
        return Assign(action)
    elif isinstance(action, LogAction):
        return Log(action)
    elif isinstance(action, IfAction):
        return create_if_action_callable(action)
    elif isinstance(action, ForeachAction):
        return create_foreach_action_callable(action)
    elif isinstance(action, SendAction):
        return create_send_action_callable(action)
    elif isinstance(action, CancelAction):
        return create_cancel_action_callable(action)
    elif isinstance(action, ScriptAction):
        return create_script_action_callable(action)
    else:
        raise ValueError(f"Unknown action type: {type(action)}")


class Assign(CallableAction):
    def __init__(self, action: AssignAction):
        super().__init__()
        self.action = action

    def __call__(self, *args, **kwargs):
        machine: StateChart = kwargs["machine"]
        if self.action.child_xml is not None:
            value = self.action.child_xml
        else:
            value = _eval(self.action.expr, **kwargs)

        *path, attr = self.action.location.split(".")
        obj = machine.model
        for p in path:
            obj = getattr(obj, p)

        if not attr.isidentifier() or not (hasattr(obj, attr) or attr in kwargs):
            raise ValueError(
                f"<assign> 'location' must be a valid Python attribute name and must be declared, "
                f"got: {self.action.location}"
            )
        if attr in protected_attrs:
            raise ValueError(
                f"<assign> 'location' cannot assign to a protected attribute: "
                f"{self.action.location}"
            )
        setattr(obj, attr, value)
        logger.debug(f"Assign: {self.action.location} = {value!r}")


class Log(CallableAction):
    def __init__(self, action: LogAction):
        super().__init__()
        self.action = action

    def __call__(self, *args, **kwargs):
        value = _eval(self.action.expr, **kwargs) if self.action.expr else None

        if self.action.label and self.action.expr is not None:
            msg = f"{self.action.label}: {value!r}"
        elif self.action.label:
            msg = f"{self.action.label}"
        else:
            msg = f"{value!r}"
        print(msg)


def create_if_action_callable(action: IfAction) -> Callable:
    branches = [
        (
            Cond.create(branch.cond),
            [create_action_callable(action) for action in branch.actions],
        )
        for branch in action.branches
    ]

    def if_action(*args, **kwargs):
        machine: StateChart = kwargs["machine"]
        for cond, actions in branches:
            try:
                cond_result = not cond or cond(*args, **kwargs)
            except Exception as e:
                # SCXML spec: condition error → treat as false, queue error.execution.
                if machine.catch_errors_as_events:
                    machine.send("error.execution", error=e, internal=True)
                    cond_result = False
                else:
                    raise
            if cond_result:
                for action in actions:
                    action(*args, **kwargs)
                return

    if_action.action = action  # type: ignore[attr-defined]
    return if_action


def create_foreach_action_callable(action: ForeachAction) -> Callable:
    child_actions = [create_action_callable(act) for act in action.content.actions]

    def foreach_action(*args, **kwargs):
        machine: StateChart = kwargs["machine"]
        try:
            # Evaluate the array expression to get the iterable
            array = _eval(action.array, **kwargs)
        except Exception as e:
            raise ValueError(f"Error evaluating <foreach> 'array' expression: {e}") from e

        if not action.item.isidentifier():
            raise ValueError(
                f"<foreach> 'item' must be a valid Python attribute name, got: {action.item}"
            )
        for index, item in enumerate(array):
            # Assign the item and optionally the index
            setattr(machine.model, action.item, item)
            if action.index:
                setattr(machine.model, action.index, index)

            # Execute child actions
            for act in child_actions:
                act(*args, **kwargs)

    foreach_action.action = action  # type: ignore[attr-defined]
    return foreach_action


def create_raise_action_callable(action: RaiseAction) -> Callable:
    def raise_action(*args, **kwargs):
        machine: StateChart = kwargs["machine"]

        Event(id=action.event, name=action.event, internal=True, _sm=machine).put()

    raise_action.action = action  # type: ignore[attr-defined]
    return raise_action


def _send_to_parent(action: SendAction, **kwargs):
    """Route a <send target="#_parent"> to the parent machine via _invoke_session."""
    machine = kwargs["machine"]
    session = getattr(machine, "_invoke_session", None)
    if session is None:
        logger.warning(
            "<send target='#_parent'> ignored: machine %r has no _invoke_session",
            machine.name,
        )
        return
    event = action.event or _eval(action.eventexpr, **kwargs)  # type: ignore[arg-type]
    names = []
    for name in (action.namelist or "").strip().split():
        if not hasattr(machine.model, name):
            raise NameError(f"Namelist variable '{name}' not found on model")
        names.append(Param(name=name, expr=name))
    params_values = {}
    for param in chain(names, action.params):
        if param.expr is None:
            continue
        params_values[param.name] = _eval(param.expr, **kwargs)
    session.send_to_parent(event, **params_values)


def _send_to_invoke(action: SendAction, invokeid: str, **kwargs):
    """Route a <send target="#_<invokeid>"> to the invoked child session."""
    machine: StateChart = kwargs["machine"]
    event = action.event or _eval(action.eventexpr, **kwargs)  # type: ignore[arg-type]
    names = []
    for name in (action.namelist or "").strip().split():
        if not hasattr(machine.model, name):
            raise NameError(f"Namelist variable '{name}' not found on model")
        names.append(Param(name=name, expr=name))
    params_values = {}
    for param in chain(names, action.params):
        if param.expr is None:
            continue
        params_values[param.name] = _eval(param.expr, **kwargs)
    if not machine._engine._invoke_manager.send_to_child(invokeid, event, **params_values):
        # Per SCXML spec: if target is not reachable → error.communication
        BoundEvent("error.communication", internal=True, _sm=machine).put()


def create_send_action_callable(action: SendAction) -> Callable:  # noqa: C901
    content: Any = ()
    _valid_targets = (None, "#_internal", "internal", "#_parent", "parent")
    if action.content:
        try:
            content = (eval(action.content, {}, {}),)
        except (NameError, SyntaxError, TypeError):
            content = (action.content,)

    def send_action(*args, **kwargs):  # noqa: C901
        machine: StateChart = kwargs["machine"]
        event = action.event or _eval(action.eventexpr, **kwargs)  # type: ignore[arg-type]
        target = action.target if action.target else None

        if action.type and action.type != "http://www.w3.org/TR/scxml/#SCXMLEventProcessor":
            # Per SCXML spec 6.2.3, unsupported type raises error.execution
            raise ValueError(
                f"Unsupported send type: {action.type}. "
                "Only 'http://www.w3.org/TR/scxml/#SCXMLEventProcessor' is supported"
            )
        if target not in _valid_targets:
            if target and target.startswith("#_scxml_"):
                # Valid SCXML session reference but undispatchable → error.communication
                BoundEvent("error.communication", internal=True, _sm=machine).put()
            elif target and target.startswith("#_"):
                # #_<invokeid> → route to invoked child session
                _send_to_invoke(action, target[2:], **kwargs)
            else:
                # Invalid target expression → error.execution (raised as exception)
                raise ValueError(f"Invalid target: {target}. Must be one of {_valid_targets}")
            return

        # Handle #_parent target — route to parent via _invoke_session
        if target == "#_parent":
            _send_to_parent(action, **kwargs)
            return

        internal = target in ("#_internal", "internal")

        send_id = None
        if action.id:
            send_id = action.id
        elif action.idlocation:
            send_id = uuid4().hex
            setattr(machine.model, action.idlocation, send_id)

        delay = ParseTime.parse_delay(action.delay, action.delayexpr, **kwargs)

        # Per SCXML spec, if namelist evaluation causes an error (e.g., variable not found),
        # the send MUST NOT be dispatched and error.execution is raised.
        names = []
        for name in (action.namelist or "").strip().split():
            if not hasattr(machine.model, name):
                raise NameError(f"Namelist variable '{name}' not found on model")
            names.append(Param(name=name, expr=name))
        params_values = {}
        for param in chain(names, action.params):
            if param.expr is None:
                continue
            params_values[param.name] = _eval(param.expr, **kwargs)

        Event(id=event, name=event, delay=delay, internal=internal, _sm=machine).put(
            *content,
            send_id=send_id,
            **params_values,
        )

    send_action.action = action  # type: ignore[attr-defined]
    return send_action


def create_cancel_action_callable(action: CancelAction) -> Callable:
    def cancel_action(*args, **kwargs):
        machine: StateChart = kwargs["machine"]
        if action.sendid:
            send_id = action.sendid
        elif action.sendidexpr:
            send_id = _eval(action.sendidexpr, **kwargs)
        else:
            raise ValueError("CancelAction must have either 'sendid' or 'sendidexpr'")
        # Implement cancel logic if necessary
        # For now, we can just print that the event is canceled
        machine.cancel_event(send_id)

    cancel_action.action = action  # type: ignore[attr-defined]
    return cancel_action


def create_script_action_callable(action: ScriptAction) -> Callable:
    def script_action(*args, **kwargs):
        machine: StateChart = kwargs["machine"]
        local_vars = {
            **machine.model.__dict__,
        }
        exec(action.content, {}, local_vars)

        # Assign the resulting variables to the state machine's model
        for var_name, value in local_vars.items():
            setattr(machine.model, var_name, value)

    script_action.action = action  # type: ignore[attr-defined]
    return script_action


def create_invoke_init_callable() -> Callable:
    """Create a callback that extracts invoke-specific kwargs and stores them on the machine.

    This is always inserted at position 0 in the initial state's onentry list by the
    SCXML processor, so that ``_invoke_session`` and ``_invoke_params`` are handled
    before any other callbacks run — even for SMs without a ``<datamodel>``.
    """
    initialized = False

    def invoke_init(*args, **kwargs):
        nonlocal initialized
        if initialized:
            return
        initialized = True
        machine = kwargs.get("machine")
        if machine is not None:
            # Use get() not pop(): each callback receives a copy of kwargs
            # (via EventData.extended_kwargs), so pop would be misleading.
            machine._invoke_params = kwargs.get("_invoke_params")
            machine._invoke_session = kwargs.get("_invoke_session")

    return invoke_init


def _create_dataitem_callable(action: DataItem) -> Callable:
    def data_initializer(**kwargs):
        machine: StateChart = kwargs["machine"]

        # Check for invoke param overrides — params from parent override child defaults
        invoke_params = getattr(machine, "_invoke_params", None)
        if invoke_params and action.id in invoke_params:
            setattr(machine.model, action.id, invoke_params[action.id])
            return

        if action.expr:
            try:
                value = _eval(action.expr, **kwargs)
            except Exception:
                setattr(machine.model, action.id, None)
                raise

        elif action.content:
            try:
                value = _eval(action.content, **kwargs)
            except Exception:
                value = action.content
        else:
            value = None

        setattr(machine.model, action.id, value)

    return data_initializer


def create_datamodel_action_callable(action: DataModel) -> "Callable | None":
    data_elements = [_create_dataitem_callable(item) for item in action.data]
    data_elements.extend([create_script_action_callable(script) for script in action.scripts])

    if not data_elements:
        return None

    initialized = False

    def datamodel(*args, **kwargs):
        nonlocal initialized
        if initialized:
            return
        initialized = True

        for act in data_elements:
            act(**kwargs)

    return datamodel


class ExecuteBlock(CallableAction):
    """Parses the children as <executable> content XML into a callable."""

    def __init__(self, content: ExecutableContent):
        super().__init__()
        self.action = content
        self.action_callables = [create_action_callable(action) for action in content.actions]

    def __call__(self, *args, **kwargs):
        for action in self.action_callables:
            action(*args, **kwargs)


class DoneDataCallable(CallableAction):
    """Evaluates <donedata> params/content and returns the data for done events."""

    def __init__(self, donedata: DoneData):
        super().__init__()
        self.action = donedata
        self.donedata = donedata

    def __call__(self, *args, **kwargs):
        if self.donedata.content_expr is not None:
            return _eval(self.donedata.content_expr, **kwargs)

        result = {}
        for param in self.donedata.params:
            if param.expr is not None:
                result[param.name] = _eval(param.expr, **kwargs)
            elif param.location is not None:  # pragma: no branch
                location = param.location.strip()
                try:
                    result[param.name] = _eval(location, **kwargs)
                except Exception as e:
                    raise ValueError(
                        f"<param> location '{location}' does not resolve to a valid value"
                    ) from e
        return result
