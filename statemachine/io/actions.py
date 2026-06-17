"""Turn neutral-IR :mod:`~statemachine.io.model` actions into executable callables.

Each :class:`~statemachine.io.model.Action` is compiled into a callable by
:func:`create_action_callable`, using an :class:`~statemachine.io.evaluators.Evaluator`
to evaluate the expression/script strings it carries (secure by default). This layer
is format-neutral: it is shared by the SCXML, JSON and YAML readers.
"""

import logging
import re
from collections.abc import Callable
from itertools import chain
from typing import Any
from uuid import uuid4

from ..event import BoundEvent
from ..event import Event
from ..statemachine import StateChart
from .evaluators import Evaluator
from .evaluators import protected_attrs
from .model import Action
from .model import AssignAction
from .model import CancelAction
from .model import DataItem
from .model import DataModel
from .model import DoneData
from .model import ExecutableContent
from .model import ForeachAction
from .model import IfAction
from .model import LogAction
from .model import Param
from .model import RaiseAction
from .model import ScriptAction
from .model import SendAction

logger = logging.getLogger(__name__)
_debug = logger.debug if logger.isEnabledFor(logging.DEBUG) else lambda *a, **k: None


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
    def create(cls, cond: "str | None", evaluator: Evaluator, processor=None):
        if cond is None:
            return None
        return cls(cond, evaluator, processor)

    def __init__(self, cond: str, evaluator: Evaluator, processor=None):
        super().__init__()
        self.action = cond
        self.processor = processor
        self._cond = evaluator.compile_bool(cond)

    def __call__(self, *args, **kwargs):
        result = self._cond(*args, **kwargs)
        _debug("Cond %s -> %s", self.action, result)
        return result


def create_action_callable(action: Action, evaluator: Evaluator) -> Callable:
    match action:
        case RaiseAction():
            return create_raise_action_callable(action)
        case AssignAction():
            return Assign(action, evaluator)
        case LogAction():
            return Log(action, evaluator)
        case IfAction():
            return create_if_action_callable(action, evaluator)
        case ForeachAction():
            return create_foreach_action_callable(action, evaluator)
        case SendAction():
            return create_send_action_callable(action, evaluator)
        case CancelAction():
            return create_cancel_action_callable(action, evaluator)
        case ScriptAction():
            return create_script_action_callable(action, evaluator)
        case _:
            raise ValueError(f"Unknown action type: {type(action)}")


class Assign(CallableAction):
    def __init__(self, action: AssignAction, evaluator: Evaluator):
        super().__init__()
        self.action = action
        self._expr = (
            evaluator.compile_value(action.expr)
            if action.child_xml is None and action.expr is not None
            else None
        )

    def __call__(self, *args, **kwargs):
        machine: StateChart = kwargs["machine"]
        if self.action.child_xml is not None:
            value = self.action.child_xml
        else:
            value = self._expr(*args, **kwargs)  # type: ignore[misc]

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
        _debug("Assign: %s = %r", self.action.location, value)


class Log(CallableAction):
    def __init__(self, action: LogAction, evaluator: Evaluator):
        super().__init__()
        self.action = action
        self._expr = evaluator.compile_value(action.expr) if action.expr else None

    def __call__(self, *args, **kwargs):
        value = self._expr(*args, **kwargs) if self._expr else None

        if self.action.label and self.action.expr is not None:
            msg = f"{self.action.label}: {value!r}"
        elif self.action.label:
            msg = f"{self.action.label}"
        else:
            msg = f"{value!r}"
        print(msg)


def create_if_action_callable(action: IfAction, evaluator: Evaluator) -> Callable:
    branches = [
        (
            Cond.create(branch.cond, evaluator),
            [create_action_callable(action, evaluator) for action in branch.actions],
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


def create_foreach_action_callable(action: ForeachAction, evaluator: Evaluator) -> Callable:
    child_actions = [create_action_callable(act, evaluator) for act in action.content.actions]
    array_expr = evaluator.compile_value(action.array)

    def foreach_action(*args, **kwargs):
        machine: StateChart = kwargs["machine"]
        try:
            # Evaluate the array expression to get the iterable
            array = array_expr(*args, **kwargs)
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

        Event(id=action.event, internal=True, _sm=machine).put()

    raise_action.action = action  # type: ignore[attr-defined]
    return raise_action


def _resolve_event_and_params(action: SendAction, evaluator: Evaluator, **kwargs):
    """Evaluate the event name, namelist and params for a <send> at call time."""
    machine = kwargs["machine"]
    event = action.event or evaluator.compile_value(action.eventexpr)(**kwargs)  # type: ignore[arg-type]
    names = []
    for name in (action.namelist or "").strip().split():
        if not hasattr(machine.model, name):
            raise NameError(f"Namelist variable '{name}' not found on model")
        names.append(Param(name=name, expr=name))
    params_values = {}
    for param in chain(names, action.params):
        if param.expr is None:
            continue
        params_values[param.name] = evaluator.compile_value(param.expr)(**kwargs)
    return event, params_values


def _send_to_parent(action: SendAction, evaluator: Evaluator, **kwargs):
    """Route a <send target="#_parent"> to the parent machine via _invoke_session."""
    machine = kwargs["machine"]
    session = getattr(machine, "_invoke_session", None)
    if session is None:
        logger.warning(
            "<send target='#_parent'> ignored: machine %r has no _invoke_session",
            machine.name,
        )
        return
    event, params_values = _resolve_event_and_params(action, evaluator, **kwargs)
    session.send_to_parent(event, **params_values)


def _send_to_invoke(action: SendAction, invokeid: str, evaluator: Evaluator, **kwargs):
    """Route a <send target="#_<invokeid>"> to the invoked child session."""
    machine: StateChart = kwargs["machine"]
    event, params_values = _resolve_event_and_params(action, evaluator, **kwargs)
    if not machine._engine._invoke_manager.send_to_child(invokeid, event, **params_values):
        # Per SCXML spec: if target is not reachable → error.communication
        BoundEvent("error.communication", internal=True, _sm=machine).put()


def create_send_action_callable(  # noqa: C901
    action: SendAction, evaluator: Evaluator
) -> Callable:
    content: Any = ()
    _valid_targets = (None, "#_internal", "internal", "#_parent", "parent")
    if action.content:
        content = (evaluator.eval_literal(action.content),)
    delay_expr = (
        evaluator.compile_value(ParseTime.replace(action.delayexpr)) if action.delayexpr else None
    )

    def send_action(*args, **kwargs):  # noqa: C901
        machine: StateChart = kwargs["machine"]
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
                _send_to_invoke(action, target[2:], evaluator, **kwargs)
            else:
                # Invalid target expression → error.execution (raised as exception)
                raise ValueError(f"Invalid target: {target}. Must be one of {_valid_targets}")
            return

        # Handle #_parent target — route to parent via _invoke_session
        if target == "#_parent":
            _send_to_parent(action, evaluator, **kwargs)
            return

        internal = target in ("#_internal", "internal")

        send_id = None
        if action.id:
            send_id = action.id
        elif action.idlocation:
            send_id = uuid4().hex
            setattr(machine.model, action.idlocation, send_id)

        delay = 0.0
        if action.delay:
            delay = ParseTime.time_in_ms(action.delay)
        elif delay_expr is not None:
            delay = ParseTime.time_in_ms(delay_expr(**kwargs))

        # Per SCXML spec, if namelist evaluation causes an error (e.g., variable not found),
        # the send MUST NOT be dispatched and error.execution is raised.
        event, params_values = _resolve_event_and_params(action, evaluator, **kwargs)

        Event(id=event, delay=delay, internal=internal, _sm=machine).put(
            *content,
            send_id=send_id,
            **params_values,
        )

    send_action.action = action  # type: ignore[attr-defined]
    return send_action


def create_cancel_action_callable(action: CancelAction, evaluator: Evaluator) -> Callable:
    sendidexpr = evaluator.compile_value(action.sendidexpr) if action.sendidexpr else None

    def cancel_action(*args, **kwargs):
        machine: StateChart = kwargs["machine"]
        if action.sendid:
            send_id = action.sendid
        elif sendidexpr is not None:
            send_id = sendidexpr(*args, **kwargs)
        else:
            raise ValueError("CancelAction must have either 'sendid' or 'sendidexpr'")
        # Implement cancel logic if necessary
        # For now, we can just print that the event is canceled
        machine.cancel_event(send_id)

    cancel_action.action = action  # type: ignore[attr-defined]
    return cancel_action


def create_script_action_callable(action: ScriptAction, evaluator: Evaluator) -> Callable:
    # In the restricted (default) evaluator this raises InvalidDefinition at parse
    # time; <script> only runs under trusted=True.
    script = evaluator.compile_script(action.content)

    def script_action(*args, **kwargs):
        script(*args, **kwargs)

    script_action.action = action  # type: ignore[attr-defined]
    return script_action


def _create_dataitem_callable(action: DataItem, evaluator: Evaluator) -> Callable:
    expr_fn = evaluator.compile_value(action.expr) if action.expr else None
    content_fn = evaluator.compile_value(action.content) if action.content else None

    def data_initializer(**kwargs):
        machine: StateChart = kwargs["machine"]

        # Check for invoke param overrides — params from parent override child defaults
        invoke_params = getattr(machine, "_invoke_params", None)
        if invoke_params and action.id in invoke_params:
            setattr(machine.model, action.id, invoke_params[action.id])
            return

        if expr_fn is not None:
            try:
                value = expr_fn(**kwargs)
            except Exception:
                setattr(machine.model, action.id, None)
                raise

        elif content_fn is not None:
            try:
                value = content_fn(**kwargs)
            except Exception:
                value = action.content
        else:
            value = None

        setattr(machine.model, action.id, value)

    return data_initializer


def create_datamodel_action_callable(action: DataModel, evaluator: Evaluator) -> "Callable | None":
    data_elements = [_create_dataitem_callable(item, evaluator) for item in action.data]
    data_elements.extend(
        [create_script_action_callable(script, evaluator) for script in action.scripts]
    )

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

    def __init__(self, content: ExecutableContent, evaluator: Evaluator):
        super().__init__()
        self.action = content
        self.action_callables = [
            create_action_callable(action, evaluator) for action in content.actions
        ]

    def __call__(self, *args, **kwargs):
        for action in self.action_callables:
            action(*args, **kwargs)


class DoneDataCallable(CallableAction):
    """Evaluates <donedata> params/content and returns the data for done events."""

    def __init__(self, donedata: DoneData, evaluator: Evaluator):
        super().__init__()
        self.action = donedata
        self.donedata = donedata
        self._content_expr = (
            evaluator.compile_value(donedata.content_expr)
            if donedata.content_expr is not None
            else None
        )
        self._params = [
            (
                param.name,
                evaluator.compile_value(param.expr)
                if param.expr is not None
                else evaluator.compile_value(param.location.strip()),  # type: ignore[union-attr]
                param.location,
            )
            for param in donedata.params
        ]

    def __call__(self, *args, **kwargs):
        if self._content_expr is not None:
            return self._content_expr(*args, **kwargs)

        result = {}
        for name, fn, location in self._params:
            if location is None:
                result[name] = fn(*args, **kwargs)
            else:
                try:
                    result[name] = fn(*args, **kwargs)
                except Exception as e:
                    raise ValueError(
                        f"<param> location '{location.strip()}' does not resolve to a valid value"
                    ) from e
        return result
