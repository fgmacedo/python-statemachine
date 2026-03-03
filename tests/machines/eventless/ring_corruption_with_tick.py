from statemachine import State
from statemachine import StateChart


class RingCorruptionWithTick(StateChart):
    resisting = State(initial=True)
    corrupted = State(final=True)

    resisting.to(corrupted, cond="is_corrupted")
    tick = resisting.to.itself(internal=True)

    ring_power = 0

    def is_corrupted(self):
        return self.ring_power > 5
