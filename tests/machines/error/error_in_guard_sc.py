from statemachine import Event
from statemachine import State
from statemachine import StateChart


class ErrorInGuardSC(StateChart):
    initial = State("initial", initial=True)
    error_state = State("error_state", final=True)

    go = initial.to(initial, cond="bad_guard") | initial.to(initial)
    error_execution = Event(initial.to(error_state), id="error.execution")

    def bad_guard(self):
        raise RuntimeError("guard failed")
