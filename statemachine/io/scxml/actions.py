import html
import logging
import re
from dataclasses import dataclass
from itertools import chain
from typing import Any
from typing import Callable
from typing import List
from uuid import uuid4

from statemachine.exceptions import InvalidDefinition
from statemachine.model import Model

from ...event import Event
from ...statemachine import StateMachine
from .parser import Action
from .parser import AssignAction
from .parser import IfAction
from .parser import LogAction
from .parser import RaiseAction
from .parser import SendAction
from .schema import CancelAction
from .schema import DataItem
from .schema import DataModel
from .schema import ExecutableContent
from .schema import ForeachAction
from .schema import Param
from .schema import ScriptAction

logger = logging.getLogger(__name__)


class ParseTime:
    pattern = re.compile(r"(\d+)?(\.\d+)?(s|ms)")

    @classmethod
    def parse_delay(cls, delay: str | None, delayexpr: str | None, **kwargs):
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


class EventDataWrapper:
    origin: str = ""
    origintype: str = "http://www.w3.org/TR/scxml/#SCXMLEventProcessor"
    """The origintype of the :ref:`Event` as specified by the SCXML namespace."""

    def __init__(self, event_data):
        self.event_data = event_data

    def __getattr__(self, name):
        return getattr(self.event_data, name)

    @property
    def name(self):
        return self.event_data.event

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


def _normalize_cond(cond: str) -> str:
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


def create_cond(cond, processor=None):
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


def create_action_callable(action: Action) -> Callable:
    if isinstance(action, RaiseAction):
        return create_raise_action_callable(action)
    elif isinstance(action, AssignAction):
        return create_assign_action_callable(action)
    elif isinstance(action, LogAction):
        return create_log_action_callable(action)
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


def create_raise_action_callable(action: RaiseAction) -> Callable:
    def raise_action(*args, **kwargs):
        machine: StateMachine = kwargs["machine"]
        machine.send(action.event)

    raise_action.action = action  # type: ignore[attr-defined]
    return raise_action


def create_assign_action_callable(action: AssignAction) -> Callable:
    def assign_action(*args, **kwargs):
        machine: StateMachine = kwargs["machine"]
        value = _eval(action.expr, **kwargs)

        *path, attr = action.location.split(".")
        obj = machine.model
        for p in path:
            obj = getattr(obj, p)

        if not attr.isidentifier():
            raise ValueError(
                f"<assign> 'location' must be a valid Python attribute name, got: {action.location}"  # noqa: E501
            )
        setattr(obj, attr, value)

    assign_action.action = action  # type: ignore[attr-defined]
    return assign_action


def create_log_action_callable(action: LogAction) -> Callable:
    def log_action(*args, **kwargs):
        machine: StateMachine = kwargs["machine"]
        kwargs.update(machine.model.__dict__)
        value = _eval(action.expr, **kwargs)

        msg = f"{action.label}: {value!r}" if action.label else f"{value!r}"
        print(msg)

    log_action.action = action  # type: ignore[attr-defined]
    return log_action


def create_if_action_callable(action: IfAction) -> Callable:
    branches = [
        (
            create_cond(branch.cond),
            [create_action_callable(action) for action in branch.actions],
        )
        for branch in action.branches
    ]

    def if_action(*args, **kwargs):
        for cond, actions in branches:
            if not cond or cond(*args, **kwargs):
                for action in actions:
                    action(*args, **kwargs)
                return

    if_action.action = action  # type: ignore[attr-defined]
    return if_action


def create_foreach_action_callable(action: ForeachAction) -> Callable:
    child_actions = [create_action_callable(act) for act in action.content.actions]

    def foreach_action(*args, **kwargs):
        machine: StateMachine = kwargs["machine"]
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


def create_send_action_callable(action: SendAction) -> Callable:
    content: Any = ()
    if action.content:
        try:
            content = (eval(action.content, {}, {}),)
        except (NameError, IndentationError, SyntaxError, TypeError):
            content = (action.content,)

    def send_action(*args, **kwargs):
        machine: StateMachine = kwargs["machine"]
        event = action.event or _eval(action.eventexpr, **kwargs)
        _target = _eval(action.target, **kwargs) if action.target else None
        if action.type and action.type != "http://www.w3.org/TR/scxml/#SCXMLEventProcessor":
            raise ValueError(
                "Only 'http://www.w3.org/TR/scxml/#SCXMLEventProcessor' event type is supported"
            )

        if action.id:
            send_id = action.id
        else:
            send_id = uuid4().hex
            if action.idlocation:
                setattr(machine.model, action.idlocation, send_id)

        delay = ParseTime.parse_delay(action.delay, action.delayexpr, **kwargs)
        names = [
            Param(name=name, expr=name)
            for name in (action.namelist or "").strip().split()
            if hasattr(machine.model, name)
        ]
        params_values = {}
        for param in chain(names, action.params):
            params_values[param.name] = _eval(param.expr, **kwargs)

        Event(id=event, name=event, delay=delay).put(
            *content,
            machine=machine,
            send_id=send_id,
            **params_values,
        )

    send_action.action = action  # type: ignore[attr-defined]
    return send_action


def create_cancel_action_callable(action: CancelAction) -> Callable:
    def cancel_action(*args, **kwargs):
        machine: StateMachine = kwargs["machine"]
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
        machine: StateMachine = kwargs["machine"]
        local_vars = {
            **machine.model.__dict__,
        }
        exec(action.content, {}, local_vars)

        # Assign the resulting variables to the state machine's model
        for var_name, value in local_vars.items():
            setattr(machine.model, var_name, value)

    script_action.action = action  # type: ignore[attr-defined]
    return script_action


def _create_dataitem_callable(action: DataItem) -> Callable:
    def data_initializer(machine: StateMachine, **kwargs):
        # Evaluate the expression if provided, or set to None
        if action.expr:
            value = _eval(action.expr, **kwargs)
        elif action.content:
            try:
                value = _eval(action.content, **kwargs)
            except Exception:
                value = action.content
        else:
            value = None

        setattr(machine.model, action.id, value)

    return data_initializer


def create_datamodel_action_callable(action: DataModel) -> Callable | None:
    data_elements = [_create_dataitem_callable(item) for item in action.data]
    data_elements.extend([create_script_action_callable(script) for script in action.scripts])

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
        for act in data_elements:
            act(machine=self)

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


def create_executable_content(content: ExecutableContent) -> Callable:
    """Parses the children as <executable> content XML into a callable."""
    action_callables = [create_action_callable(action) for action in content.actions]

    def execute_block(*args, **kwargs):
        machine: StateMachine = kwargs["machine"]
        try:
            for action in action_callables:
                action(*args, **kwargs)

            machine._processing_loop()
        except Exception as e:
            logger.debug("Error executing actions", exc_info=True)
            if isinstance(e, InvalidDefinition):
                raise
            machine.send("error.execution", error=e)

    execute_block.content = content  # type: ignore[attr-defined]
    return execute_block
