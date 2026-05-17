from dataclasses import dataclass
from dataclasses import field
from typing import Literal
from urllib.parse import ParseResult


@dataclass
class Action:
    def __str__(self):
        return f"{self.__class__.__name__}"


@dataclass
class ExecutableContent:
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
    location: str
    expr: "str | None" = None
    child_xml: "str | None" = None


@dataclass
class LogAction(Action):
    label: "str | None"
    expr: "str | None"


@dataclass
class IfBranch(Action):
    cond: "str | None"
    actions: list[Action] = field(default_factory=list)

    def __str__(self):
        return self.cond or "<empty cond>"

    def append(self, action: Action):
        self.actions.append(action)


@dataclass
class IfAction(Action):
    branches: list[IfBranch] = field(default_factory=list)


@dataclass
class ForeachAction(Action):
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
    target: "str | None" = None
    internal: bool = False
    initial: bool = False
    event: "str | None" = None
    cond: "str | None" = None
    on: "ExecutableContent | None" = None


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
    content: "str | None" = None
    finalize: "ExecutableContent | None" = None


@dataclass
class State:
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


@dataclass
class HistoryState:
    id: str
    type: "Literal['shallow', 'deep']" = "shallow"
    transitions: list[Transition] = field(default_factory=list)


@dataclass
class DataItem:
    id: str
    src: "ParseResult | None"
    expr: "str | None"
    content: "str | None"


@dataclass
class DataModel:
    data: list[DataItem] = field(default_factory=list)
    scripts: list[ScriptAction] = field(default_factory=list)


@dataclass
class StateMachineDefinition:
    name: "str | None" = None
    states: dict[str, State] = field(default_factory=dict)
    initial_states: list[str] = field(default_factory=list)
    datamodel: "DataModel | None" = None
