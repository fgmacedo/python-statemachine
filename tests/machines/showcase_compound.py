from statemachine import State
from statemachine import StateChart


class CompoundSC(StateChart):
    class active(State.Compound, name="Active"):
        idle = State(initial=True)
        working = State()
        begin = idle.to(working)

    off = State(initial=True)
    done = State(final=True)

    turn_on = off.to(active)
    turn_off = active.to(done)
