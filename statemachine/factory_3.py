from .factory import StateMachineMetaclass
from .statemachine import BaseStateMachine


class StateMachine(BaseStateMachine, metaclass=StateMachineMetaclass):
    pass
