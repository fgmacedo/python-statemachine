from statemachine import State
from statemachine import StateChart


class ValidatorFallthrough(StateChart):
    """Machine with multiple transitions for the same event.

    When the first transition's validator rejects, the exception propagates
    immediately — the engine does NOT fall through to the next transition.
    """

    idle = State(initial=True)
    path_a = State(final=True)
    path_b = State(final=True)

    go = idle.to(path_a, validators="must_be_premium") | idle.to(path_b)

    def must_be_premium(self, **kwargs):
        if not kwargs.get("premium"):
            raise PermissionError("Premium required")
