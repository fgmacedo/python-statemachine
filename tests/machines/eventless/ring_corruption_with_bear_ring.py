from statemachine import State
from statemachine import StateChart


class RingCorruptionWithBearRing(StateChart):
    resisting = State(initial=True)
    corrupted = State(final=True)

    resisting.to(corrupted, cond="is_corrupted")
    bear_ring = resisting.to.itself(internal=True, on="increase_power")

    ring_power = 0

    def is_corrupted(self):
        return self.ring_power > 5

    def increase_power(self):
        self.ring_power += 2
