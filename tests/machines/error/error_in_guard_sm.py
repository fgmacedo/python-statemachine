from statemachine import State
from statemachine import StateChart


class ErrorInGuardSM(StateChart):
    """StateChart subclass with catch_errors_as_events=False: exceptions should propagate."""

    catch_errors_as_events = False

    initial = State("initial", initial=True)

    go = initial.to(initial, cond="bad_guard") | initial.to(initial)

    def bad_guard(self):
        raise RuntimeError("guard failed")
