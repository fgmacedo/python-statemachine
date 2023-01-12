# pragma: no cover
from .factory import StateMachineMetaclass
from .statemachine import BaseStateMachine


class StateMachine(BaseStateMachine):  # pragma: no cover
    __metaclass__ = StateMachineMetaclass
