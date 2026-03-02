from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import List
from typing import Set


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
    actions: List[DiagramAction] = field(default_factory=list)
    children: List["DiagramState"] = field(default_factory=list)
    is_active: bool = False
    is_parallel_area: bool = False
    is_initial: bool = False


@dataclass
class DiagramTransition:
    source: str
    targets: List[str] = field(default_factory=list)
    event: str = ""
    guards: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    is_internal: bool = False
    is_initial: bool = False


@dataclass
class DiagramGraph:
    name: str
    states: List[DiagramState] = field(default_factory=list)
    transitions: List[DiagramTransition] = field(default_factory=list)
    compound_state_ids: Set[str] = field(default_factory=set)
    bidirectional_compound_ids: Set[str] = field(default_factory=set)
