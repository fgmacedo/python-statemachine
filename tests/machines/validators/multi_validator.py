from statemachine import State
from statemachine import StateChart


class MultiValidator(StateChart):
    """Machine with multiple validators — first failure stops the chain."""

    idle = State(initial=True)
    active = State(final=True)

    start = idle.to(active, validators=["check_a", "check_b"])

    def check_a(self, **kwargs):
        if not kwargs.get("a_ok"):
            raise ValueError("A failed")

    def check_b(self, **kwargs):
        if not kwargs.get("b_ok"):
            raise ValueError("B failed")
