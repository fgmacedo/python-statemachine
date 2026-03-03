from statemachine import State
from statemachine import StateChart


class RingCorruption(StateChart):
    resisting = State(initial=True)
    corrupted = State(final=True)

    # eventless: no event name
    resisting.to(corrupted, cond="is_corrupted")

    ring_power = 0

    def is_corrupted(self):
        return self.ring_power > 5

    def increase_power(self):
        self.ring_power += 3
