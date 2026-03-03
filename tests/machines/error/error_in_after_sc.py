from statemachine import Event
from statemachine import State
from statemachine import StateChart


class ErrorInAfterSC(StateChart):
    s1 = State("s1", initial=True)
    s2 = State("s2")
    error_state = State("error_state", final=True)

    go = s1.to(s2, after="bad_after")
    error_execution = Event(s2.to(error_state), id="error.execution")

    def bad_after(self):
        raise RuntimeError("after failed")
