from dataclasses import dataclass
from dataclasses import field
from enum import Enum


class StateType(Enum):
    INITIAL = "initial"
    REGULAR = "regular"
    FINAL = "final"
    HISTORY_SHALLOW = "history_shallow"
    HISTORY_DEEP = "history_deep"
    CHOICE = "choice"
    FORK = "fork"
    JOIN = "join"
    JUNCTION = "junction"
    PARALLEL = "parallel"
    TERMINATE = "terminate"


class ActionType(Enum):
    ENTRY = "entry"
    EXIT = "exit"
    INTERNAL = "internal"


@dataclass
class DiagramAction:
    type: ActionType
    body: str


@dataclass
class DiagramState:
    id: str
    name: str
    type: StateType
    actions: list[DiagramAction] = field(default_factory=list)
    children: list["DiagramState"] = field(default_factory=list)
    is_active: bool = False
    is_parallel_area: bool = False
    is_initial: bool = False


@dataclass
class DiagramTransition:
    source: str
    targets: list[str] = field(default_factory=list)
    event: str = ""
    guards: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    is_internal: bool = False
    is_initial: bool = False


@dataclass
class DiagramGraph:
    name: str
    states: list[DiagramState] = field(default_factory=list)
    transitions: list[DiagramTransition] = field(default_factory=list)
    compound_state_ids: set[str] = field(default_factory=set)
    bidirectional_compound_ids: set[str] = field(default_factory=set)
