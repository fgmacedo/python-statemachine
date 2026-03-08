from statemachine import State
from statemachine import StateChart


class SimpleSC(StateChart):
    """A simple three-state machine.

    {statechart:rst}
    """

    idle = State(initial=True)
    running = State()
    done = State(final=True)

    start = idle.to(running)
    finish = running.to(done)
