from statemachine import State
from statemachine import StateChart


class GuardSC(StateChart):
    pending = State(initial=True)
    approved = State(final=True)
    rejected = State(final=True)

    def is_valid(self):
        return True

    def is_invalid(self):
        return False

    review = pending.to(approved, cond="is_valid") | pending.to(rejected, cond="is_invalid")
