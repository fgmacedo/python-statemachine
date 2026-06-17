"""Format-neutral intermediate representation (IR) of a statechart.

These dataclasses are the common target every format reader (SCXML, JSON, YAML)
produces, and the single input the :class:`~statemachine.io.processor.GenericProcessor`
consumes to build a :class:`~statemachine.statemachine.StateChart` class. They carry
the *structure* of a statechart (states, transitions, executable content, datamodel)
as plain data, with expressions kept as un-evaluated strings; turning those strings
into callables is the evaluator's job, not the IR's.

The vocabulary mirrors the SCXML semantic model (the formalism this library
standardizes on) plus a few optional callback-reference fields used by the native
JSON/YAML format to integrate with methods on a bound model.
"""

from dataclasses import dataclass
from dataclasses import field
from typing import Literal


@dataclass
class Action:
    def __str__(self):
        return f"{self.__class__.__name__}"


@dataclass
class ExecutableContent:
    """An ordered block of actions (the body of an ``onentry``/``onexit``/transition).

    A state may carry several blocks (SCXML allows multiple ``<onentry>`` elements),
    which is why ``State.onentry``/``onexit`` are *lists* of ``ExecutableContent``.
    """

    actions: list[Action] = field(default_factory=list)

    def __str__(self):
        return ", ".join(str(action) for action in self.actions)

    @property
    def is_empty(self):
        return not self.actions


@dataclass
class RaiseAction(Action):
    event: str


@dataclass
class AssignAction(Action):
    """Assign a value to a datamodel location (``location = expr``).

    ``location`` is a dotted attribute path on the model (e.g. ``user.name``).
    ``expr`` is the value expression; when it is ``None``, ``child_xml`` carries the
    literal inline XML/text assigned instead (SCXML ``<assign>`` with element body).
    """

    location: str
    expr: "str | None" = None
    child_xml: "str | None" = None


@dataclass
class LogAction(Action):
    label: "str | None"
    expr: "str | None"


@dataclass
class IfBranch(Action):
    """One branch of an :class:`IfAction`.

    ``cond`` is the guard expression for this branch. A ``cond`` of ``None`` marks the
    final ``else`` branch, which always matches.
    """

    cond: "str | None"
    actions: list[Action] = field(default_factory=list)

    def __str__(self):
        return self.cond or "<empty cond>"

    def append(self, action: Action):
        self.actions.append(action)


@dataclass
class IfAction(Action):
    """An ``if``/``elif``/``else`` chain.

    ``branches`` is ordered and evaluated top to bottom; the first branch whose ``cond``
    is truthy runs its actions and the rest are skipped. By convention the first branch
    is the ``if``, intermediate branches with a ``cond`` are ``elif``, and a trailing
    branch with ``cond=None`` is the ``else`` (see :class:`IfBranch`).
    """

    branches: list[IfBranch] = field(default_factory=list)


@dataclass
class ForeachAction(Action):
    """Iterate ``item`` (and optional ``index``) over the iterable ``array`` evaluates to,
    running ``content`` once per element."""

    array: str
    item: str
    index: "str | None"
    content: ExecutableContent


@dataclass
class Param:
    name: str
    expr: "str | None"
    location: "str | None" = None


@dataclass
class SendAction(Action):
    event: "str | None" = None
    eventexpr: "str | None" = None
    target: "str | None" = None
    type: "str | None" = None
    id: "str | None" = None
    idlocation: "str | None" = None
    delay: "str | None" = None
    delayexpr: "str | None" = None
    namelist: "str | None" = None
    params: list[Param] = field(default_factory=list)
    content: "str | None" = None


@dataclass
class CancelAction(Action):
    sendid: "str | None" = None
    sendidexpr: "str | None" = None


@dataclass
class ScriptAction(Action):
    content: str


@dataclass
class Transition:
    """A transition out of a state.

    Two attributes carry non-obvious conventions:

    - ``event=None`` makes the transition **eventless**: it fires automatically
      whenever ``cond`` holds (the SCXML NULL transition), instead of on a named event.
    - ``target=None`` makes it **targetless**: taking it runs ``on`` but does not change
      the active configuration (a self-action with no state change).

    ``cond``/``unless`` are guard expressions and may be a single string or a list (all
    must hold). ``on`` is the executable content run when the transition is taken.
    """

    target: "str | None" = None
    internal: bool = False
    initial: bool = False
    event: "str | None" = None
    cond: "str | None | list" = None
    on: "ExecutableContent | None" = None
    unless: "str | None | list" = None
    """Negated guard expression (or list); allowed only if falsy. Native format only."""
    on_refs: list = field(default_factory=list)
    """Extra ``on`` callbacks referenced by name. Native JSON/YAML format only (the SCXML
    reader leaves it empty)."""
    before: "ExecutableContent | None" = None
    """``before`` executable content (the library lifecycle slot that runs once the guards
    pass, before the state change). Native format only; SCXML has no equivalent slot."""
    before_refs: list = field(default_factory=list)
    """Extra ``before`` callbacks referenced by name. Native format only."""
    after: "ExecutableContent | None" = None
    """``after`` executable content (runs after the configuration has settled). Native
    format only; SCXML has no equivalent slot."""
    after_refs: list = field(default_factory=list)
    """Extra ``after`` callbacks referenced by name. Native format only."""


@dataclass
class DoneData:
    params: list[Param] = field(default_factory=list)
    content_expr: "str | None" = None


@dataclass
class InvokeDefinition:
    type: "str | None" = None
    typeexpr: "str | None" = None
    src: "str | None" = None
    srcexpr: "str | None" = None
    id: "str | None" = None
    idlocation: "str | None" = None
    autoforward: bool = False
    namelist: "str | None" = None
    params: list[Param] = field(default_factory=list)
    content: "str | StateMachineDefinition | None" = None
    """Inline child content. A string (inline SCXML, or an expression to evaluate) or, for
    the native format, an already-parsed :class:`StateMachineDefinition`."""
    finalize: "ExecutableContent | None" = None


@dataclass
class State:
    """A state node.

    ``parallel`` marks an orthogonal region (all child states are active at once);
    ``final`` marks an accepting state (which may carry ``donedata``). ``states`` holds
    nested children (compound state), keyed by id.
    """

    id: str
    initial: bool = False
    final: bool = False
    parallel: bool = False
    transitions: list[Transition] = field(default_factory=list)
    onentry: list[ExecutableContent] = field(default_factory=list)
    onexit: list[ExecutableContent] = field(default_factory=list)
    states: dict[str, "State"] = field(default_factory=dict)
    history: dict[str, "HistoryState"] = field(default_factory=dict)
    donedata: "DoneData | None" = None
    invocations: list[InvokeDefinition] = field(default_factory=list)
    enter_refs: list = field(default_factory=list)
    """``enter`` callbacks referenced by name, appended after the ``onentry`` content.
    Native JSON/YAML format only (the SCXML reader leaves it empty)."""
    exit_refs: list = field(default_factory=list)
    """``exit`` callbacks referenced by name, appended after the ``onexit`` content.
    Native format only."""


@dataclass
class HistoryState:
    id: str
    type: "Literal['shallow', 'deep']" = "shallow"
    transitions: list[Transition] = field(default_factory=list)


@dataclass
class DataItem:
    """A datamodel variable initializer (``id``), from ``expr``, inline ``content`` or
    an external ``src`` location (kept as a raw string; URL parsing happens in the reader)."""

    id: str
    src: "str | None"
    expr: "str | None"
    content: "str | None"


@dataclass
class DataModel:
    data: list[DataItem] = field(default_factory=list)
    scripts: list[ScriptAction] = field(default_factory=list)


@dataclass
class StateMachineDefinition:
    """Top-level, format-neutral statechart definition produced by every reader.

    ``initial_states`` is a list because the initial configuration may name several
    states at once (one per parallel region).
    """

    name: "str | None" = None
    states: dict[str, State] = field(default_factory=dict)
    initial_states: list[str] = field(default_factory=list)
    datamodel: "DataModel | None" = None
