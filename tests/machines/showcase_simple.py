from statemachine import State
from statemachine import StateChart


class SimpleSC(StateChart):
    idle = State(initial=True)
    running = State()
    done = State(final=True)

    start = idle.to(running)
    finish = running.to(done)
