from statemachine import State
from statemachine import StateChart


class InternalSC(StateChart):
    monitoring = State(initial=True)
    done = State(final=True)

    def log_status(self): ...

    check = monitoring.to.itself(internal=True, on="log_status")
    stop = monitoring.to(done)
