from statemachine import State
from statemachine import StateChart


class ValidatorWithCond(StateChart):
    """Machine that combines validators and conditions on the same transition."""

    idle = State(initial=True)
    active = State(final=True)

    start = idle.to(active, validators="check_auth", cond="has_permission")

    has_permission = False

    def check_auth(self, token=None, **kwargs):
        if token != "valid":
            raise PermissionError("Invalid token")
