from statemachine import Event
from statemachine import State
from statemachine import StateChart


class ErrorConventionEventSC(StateChart):
    """Using Event without explicit id with error_ prefix auto-registers dot notation."""

    s1 = State("s1", initial=True)
    error_state = State("error_state", final=True)

    go = s1.to(s1, on="bad_action")
    error_execution = Event(s1.to(error_state))

    def bad_action(self):
        raise RuntimeError("action failed")
