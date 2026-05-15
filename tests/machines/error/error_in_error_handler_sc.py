from statemachine import Event
from statemachine import State
from statemachine import StateChart


class ErrorInErrorHandlerSC(StateChart):
    """Error in error.execution handler should not cause infinite loop."""

    s1 = State("s1", initial=True)
    s2 = State("s2")
    s3 = State("s3", final=True)

    go = s1.to(s2, on="bad_action")
    finish = s2.to(s3)
    error_execution = Event(
        s1.to(s1, on="bad_error_handler") | s2.to(s2, on="bad_error_handler"),
        id="error.execution",
    )

    def bad_action(self):
        raise RuntimeError("action failed")

    def bad_error_handler(self):
        raise RuntimeError("error handler also failed")
