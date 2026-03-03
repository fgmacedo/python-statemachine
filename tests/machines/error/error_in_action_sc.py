from statemachine import Event
from statemachine import State
from statemachine import StateChart


class ErrorInActionSC(StateChart):
    s1 = State("s1", initial=True)
    s2 = State("s2")
    error_state = State("error_state", final=True)

    go = s1.to(s2, on="bad_action")
    error_execution = Event(s1.to(error_state) | s2.to(error_state), id="error.execution")

    def bad_action(self):
        raise RuntimeError("action failed")
