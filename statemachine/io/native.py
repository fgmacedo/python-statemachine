"""Translate the native declarative dict syntax into the neutral IR.

This is the shared core of the JSON and YAML readers: both parse their text into a
plain Python ``dict`` and hand it to :func:`native_dict_to_definition`, which builds
a :class:`~statemachine.io.model.StateMachineDefinition`.

The surface syntax uses the library's own vocabulary (``states`` as a mapping keyed
by id, ``transitions`` as a single list with optional ``event``, ``enter``/``exit``/
``on`` actions, ``cond``/``unless`` guards) plus a structured action vocabulary with
SCXML parity (``assign``/``raise``/``log``/``if``/``foreach``/``send``/``cancel``/
``script``). A bare string in an action position is treated as a callback reference
(a method on the bound model). Guards and expressions are kept as strings; the
processor compiles them with the (secure-by-default) evaluator.
"""

from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any

from ..exceptions import InvalidDefinition
from .model import Action
from .model import AssignAction
from .model import CancelAction
from .model import DataItem
from .model import DataModel
from .model import DoneData
from .model import ExecutableContent
from .model import ForeachAction
from .model import HistoryState
from .model import IfAction
from .model import IfBranch
from .model import InvokeDefinition
from .model import LogAction
from .model import Param
from .model import RaiseAction
from .model import ScriptAction
from .model import SendAction
from .model import State
from .model import StateMachineDefinition
from .model import Transition

_ACTION_KEYS = {"assign", "raise", "log", "if", "foreach", "send", "cancel", "script"}

# Allowed keys per container node. These are the single source of truth for the parser's
# accepted vocabulary and are asserted equal to the JSON Schema in tests/io/test_validation.py,
# so the schema and the parser can never silently drift apart.
_DOCUMENT_KEYS = frozenset({"name", "description", "datamodel", "states"})
_STATE_KEYS = frozenset(
    {
        "initial",
        "final",
        "parallel",
        "enter",
        "exit",
        "transitions",
        "invoke",
        "states",
        "history",
        "donedata",
    }
)
_TRANSITION_KEYS = frozenset(
    {"event", "target", "cond", "unless", "internal", "initial", "on", "before", "after"}
)
_INVOKE_KEYS = frozenset(
    {
        "type",
        "typeexpr",
        "src",
        "srcexpr",
        "id",
        "idlocation",
        "autoforward",
        "namelist",
        "params",
        "content",
        "finalize",
    }
)

_TRUE_STRINGS = {"true", "yes", "on", "1"}
_FALSE_STRINGS = {"false", "no", "off", "0", ""}


def _flag(value) -> bool:
    """Coerce a flag value to bool, accepting bool or common string spellings."""
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _TRUE_STRINGS:
            return True
        if token in _FALSE_STRINGS:
            return False
        raise InvalidDefinition(f"Expected a boolean flag, got {value!r}.")
    return bool(value)


def _check_keys(node: Mapping, allowed: "frozenset[str]", kind: str) -> None:
    """Reject keys outside the declared vocabulary, mirroring the schema's strictness."""
    unknown = sorted(set(node) - allowed)
    if unknown:
        raise InvalidDefinition(
            f"Unknown {kind} key(s) {unknown}; allowed keys are {sorted(allowed)}."
        )


def native_dict_to_definition(
    doc: Mapping, *, source_name: "str | None" = None
) -> StateMachineDefinition:
    """Build a :class:`StateMachineDefinition` from the native dict syntax."""
    if not isinstance(doc, Mapping):
        raise InvalidDefinition(
            f"Statechart definition must be a mapping, got {type(doc).__name__}."
        )
    _check_keys(doc, _DOCUMENT_KEYS, "document")
    states_doc = doc.get("states")
    if not isinstance(states_doc, Mapping) or not states_doc:
        raise InvalidDefinition("Statechart definition must have a non-empty 'states' mapping.")

    states: dict[str, State] = {}
    initial_states: list[str] = []
    for state_id, state_def in states_doc.items():
        state = _parse_state(state_id, state_def or {})
        states[state_id] = state
        if state.initial:
            initial_states.append(state_id)

    # If no initial state was declared, pick the first one (mirrors the SCXML reader).
    if not initial_states and states:
        first = next(iter(states))
        states[first].initial = True
        initial_states.append(first)

    return StateMachineDefinition(
        name=doc.get("name") or source_name,
        states=states,
        initial_states=initial_states,
        datamodel=_parse_datamodel(doc.get("datamodel")),
    )


def _parse_state(state_id: str, sdef: Mapping) -> State:
    if not isinstance(sdef, Mapping):
        raise InvalidDefinition(f"State {state_id!r} definition must be a mapping.")
    _check_keys(sdef, _STATE_KEYS, f"state {state_id!r}")

    state = State(
        id=state_id,
        initial=_flag(sdef.get("initial")),
        final=_flag(sdef.get("final")),
        parallel=_flag(sdef.get("parallel")),
    )

    enter_content, state.enter_refs = _parse_actions(sdef.get("enter"))
    if not enter_content.is_empty:
        state.onentry.append(enter_content)
    exit_content, state.exit_refs = _parse_actions(sdef.get("exit"))
    if not exit_content.is_empty:
        state.onexit.append(exit_content)

    for item in sdef.get("transitions", []) or []:
        state.transitions.append(_parse_transition(item))

    for child_id, child_def in (sdef.get("states") or {}).items():
        state.states[child_id] = _parse_state(child_id, child_def or {})

    for hist_id, hist_def in (sdef.get("history") or {}).items():
        state.history[hist_id] = _parse_history(hist_id, hist_def or {})

    invoke_value = sdef.get("invoke")
    if invoke_value:
        items = [invoke_value] if isinstance(invoke_value, Mapping) else invoke_value
        for item in items:
            state.invocations.append(_parse_invoke(item))

    if state.final and "donedata" in sdef:
        state.donedata = _parse_donedata(sdef["donedata"])

    return state


def _parse_invoke(item: Mapping) -> InvokeDefinition:
    """Parse a native ``invoke`` entry.

    ``content`` may be an inline child statechart (a mapping, parsed eagerly into a neutral
    definition) or an expression string; ``src``/``srcexpr`` reference a child document in
    the same format. ``finalize`` is structured executable content.
    """
    if not isinstance(item, Mapping):
        raise InvalidDefinition(f"Invoke entry must be a mapping, got {type(item).__name__}.")
    _check_keys(item, _INVOKE_KEYS, "invoke")

    content = item.get("content")
    if isinstance(content, Mapping):
        content = native_dict_to_definition(content)

    params = [
        Param(name=p["name"], expr=p.get("expr"), location=p.get("location"))
        for p in (item.get("params") or [])
    ]
    finalize_actions = _parse_action_list(item.get("finalize"))

    return InvokeDefinition(
        type=item.get("type"),
        typeexpr=item.get("typeexpr"),
        src=item.get("src"),
        srcexpr=item.get("srcexpr"),
        id=item.get("id"),
        idlocation=item.get("idlocation"),
        autoforward=_flag(item.get("autoforward")),
        namelist=item.get("namelist"),
        params=params,
        content=content,
        finalize=ExecutableContent(actions=finalize_actions) if finalize_actions else None,
    )


def _parse_history(hist_id: str, hdef: Mapping) -> HistoryState:
    history = HistoryState(id=hist_id, type=hdef.get("type", "shallow"))
    for item in hdef.get("transitions", []) or []:
        history.transitions.append(_parse_transition(item))
    return history


def _parse_transition(item: Mapping) -> Transition:
    if not isinstance(item, Mapping):
        raise InvalidDefinition(f"Transition must be a mapping, got {type(item).__name__}.")
    _check_keys(item, _TRANSITION_KEYS, "transition")
    transition = Transition(
        target=item.get("target"),
        event=item.get("event"),
        internal=_flag(item.get("internal")),
        initial=_flag(item.get("initial")),
        cond=item.get("cond"),
        unless=item.get("unless"),
    )
    on_content, transition.on_refs = _parse_actions(item.get("on"))
    if not on_content.is_empty:
        transition.on = on_content
    before_content, transition.before_refs = _parse_actions(item.get("before"))
    if not before_content.is_empty:
        transition.before = before_content
    after_content, transition.after_refs = _parse_actions(item.get("after"))
    if not after_content.is_empty:
        transition.after = after_content
    return transition


def _parse_datamodel(value) -> "DataModel | None":
    if not value:
        return None
    data_model = DataModel()
    # Accept either a list of {id, expr/content} or a mapping {id: expr}.
    if isinstance(value, Mapping):
        items = [{"id": k, "expr": v} for k, v in value.items()]
    else:
        items = list(value)
    for item in items:
        data_model.data.append(
            DataItem(
                id=item["id"],
                src=item.get("src"),
                expr=item.get("expr"),
                content=item.get("content"),
            )
        )
    return data_model if data_model.data else None


def _parse_donedata(value: Mapping) -> DoneData:
    params = [
        Param(name=p["name"], expr=p.get("expr"), location=p.get("location"))
        for p in (value.get("params") or [])
    ]
    return DoneData(params=params, content_expr=value.get("content"))


def _as_list(value) -> list:
    """Normalize a single action or a list of actions into a list."""
    if value is None:
        return []
    if isinstance(value, (str, Mapping)):
        return [value]
    if isinstance(value, Sequence):
        return list(value)
    raise InvalidDefinition(
        f"Expected an action, a list, or a string, got {type(value).__name__}."
    )


def _parse_actions(value) -> "tuple[ExecutableContent, list]":
    """Split an action value into executable content and bare callback references."""
    actions = []
    refs: list = []
    for item in _as_list(value):
        if isinstance(item, str):
            refs.append(item)
        elif isinstance(item, Mapping):
            actions.append(_parse_action_node(item))
        else:
            raise InvalidDefinition(
                f"Action must be a string or a mapping, got {type(item).__name__}."
            )
    return ExecutableContent(actions=actions), refs


def _parse_action_list(value) -> list:
    """Parse nested actions (inside ``if``/``foreach``); callback refs are not allowed here."""
    content, refs = _parse_actions(value)
    if refs:
        raise InvalidDefinition(
            f"Callback references {refs!r} are not allowed inside if/foreach branches; "
            "use a structured action instead."
        )
    return content.actions


def _parse_action_node(node: Mapping):
    keys = _ACTION_KEYS & set(node)
    if len(keys) != 1:
        raise InvalidDefinition(
            f"Each action must have exactly one of {sorted(_ACTION_KEYS)} as its key, "
            f"got keys {sorted(node)}."
        )
    kind = keys.pop()
    body = node[kind]
    return _ACTION_BUILDERS[kind](body)


def _build_assign(body: Mapping) -> AssignAction:
    return AssignAction(location=body["location"], expr=body.get("expr"))


def _build_raise(body) -> RaiseAction:
    event = body if isinstance(body, str) else body["event"]
    return RaiseAction(event=event)


def _build_log(body) -> LogAction:
    if isinstance(body, str):
        return LogAction(label=None, expr=body)
    return LogAction(label=body.get("label"), expr=body.get("expr"))


def _build_script(body: str) -> ScriptAction:
    return ScriptAction(content=body)


def _build_cancel(body: Mapping) -> CancelAction:
    return CancelAction(sendid=body.get("sendid"), sendidexpr=body.get("sendidexpr"))


def _build_foreach(body: Mapping) -> ForeachAction:
    return ForeachAction(
        array=body["array"],
        item=body["item"],
        index=body.get("index"),
        content=ExecutableContent(actions=_parse_action_list(body.get("do"))),
    )


def _build_send(body: Mapping) -> SendAction:
    params = [
        Param(name=p["name"], expr=p.get("expr"), location=p.get("location"))
        for p in (body.get("params") or [])
    ]
    return SendAction(
        event=body.get("event"),
        eventexpr=body.get("eventexpr"),
        target=body.get("target"),
        type=body.get("type"),
        id=body.get("id"),
        idlocation=body.get("idlocation"),
        delay=body.get("delay"),
        delayexpr=body.get("delayexpr"),
        namelist=body.get("namelist"),
        params=params,
        content=body.get("content"),
    )


def _build_if(body: Mapping) -> IfAction:
    branches = [IfBranch(cond=body["cond"], actions=_parse_action_list(body.get("then")))]
    for elif_branch in body.get("elif", []) or []:
        branches.append(
            IfBranch(cond=elif_branch["cond"], actions=_parse_action_list(elif_branch.get("then")))
        )
    if "else" in body:
        branches.append(IfBranch(cond=None, actions=_parse_action_list(body["else"])))
    return IfAction(branches=branches)


_ACTION_BUILDERS: "dict[str, Callable[[Any], Action]]" = {
    "assign": _build_assign,
    "raise": _build_raise,
    "log": _build_log,
    "script": _build_script,
    "cancel": _build_cancel,
    "foreach": _build_foreach,
    "send": _build_send,
    "if": _build_if,
}
