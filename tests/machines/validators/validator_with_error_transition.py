from statemachine import State
from statemachine import StateChart


class ValidatorWithErrorTransition(StateChart):
    """Machine with both a validator and an error.execution transition.

    The error.execution transition should NOT be triggered by validator
    rejection — only by actual execution errors in actions.
    """

    idle = State(initial=True)
    active = State()
    error_state = State(final=True)

    start = idle.to(active, validators="check_input")
    do_work = active.to.itself(on="risky_action")
    error_execution = active.to(error_state)

    def check_input(self, value=None, **kwargs):
        if value is None:
            raise ValueError("Input required")

    def risky_action(self, **kwargs):
        raise RuntimeError("Boom")
