from .factory import StateMachineMetaclass
from .statemachine import BaseStateMachine


class StateMachine(BaseStateMachine):
    __metaclass__ = StateMachineMetaclass
