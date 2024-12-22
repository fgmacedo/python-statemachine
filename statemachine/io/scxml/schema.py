from dataclasses import dataclass
from dataclasses import field
from typing import Dict
from typing import List
from typing import Set


@dataclass
class Action:
    pass

    def __str__(self):
        return f"{self.__class__.__name__}"


@dataclass
class ExecutableContent:
    actions: List[Action] = field(default_factory=list)

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
    expr: str


@dataclass
class LogAction(Action):
    label: "str | None"
    expr: str


@dataclass
class IfBranch(Action):
    cond: "str | None"
    actions: List[Action] = field(default_factory=list)

    def __str__(self):
        return self.cond

    def append(self, action: Action):
        self.actions.append(action)


@dataclass
class IfAction(Action):
    branches: List[IfBranch] = field(default_factory=list)


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
    params: List[Param] = field(default_factory=list)
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
class State:
    id: str
    initial: bool = False
    final: bool = False
    parallel: bool = False
    transitions: List[Transition] = field(default_factory=list)
    onentry: List[ExecutableContent] = field(default_factory=list)
    onexit: List[ExecutableContent] = field(default_factory=list)
    states: Dict[str, "State"] = field(default_factory=dict)


@dataclass
class DataItem:
    id: str
    src: "str | None"
    expr: "str | None"
    content: "str | None"


@dataclass
class DataModel:
    data: List[DataItem] = field(default_factory=list)
    scripts: List[ScriptAction] = field(default_factory=list)


@dataclass
class StateMachineDefinition:
    name: "str | None" = None
    states: Dict[str, State] = field(default_factory=dict)
    initial_states: Set[str] = field(default_factory=set)
    datamodel: "DataModel | None" = None
