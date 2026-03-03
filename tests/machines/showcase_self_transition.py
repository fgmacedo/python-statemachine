from statemachine import State
from statemachine import StateChart


class SelfTransitionSC(StateChart):
    counting = State(initial=True)
    done = State(final=True)

    increment = counting.to.itself()
    stop = counting.to(done)
