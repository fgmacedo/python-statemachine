import pytest

from statemachine import Event
from statemachine import State
from statemachine import StateChart
from statemachine import StateMachine
from statemachine.exceptions import InvalidDefinition


class ErrorInGuardSC(StateChart):
    initial = State("initial", initial=True)
    error_state = State("error_state", final=True)

    go = initial.to(initial, cond="bad_guard") | initial.to(initial)
    error_execution = Event(initial.to(error_state), id="error.execution")

    def bad_guard(self):
        raise RuntimeError("guard failed")


class ErrorInOnEnterSC(StateChart):
    s1 = State("s1", initial=True)
    s2 = State("s2")
    error_state = State("error_state", final=True)

    go = s1.to(s2)
    error_execution = Event(s1.to(error_state) | s2.to(error_state), id="error.execution")

    def on_enter_s2(self):
        raise RuntimeError("on_enter failed")


class ErrorInActionSC(StateChart):
    s1 = State("s1", initial=True)
    s2 = State("s2")
    error_state = State("error_state", final=True)

    go = s1.to(s2, on="bad_action")
    error_execution = Event(s1.to(error_state) | s2.to(error_state), id="error.execution")

    def bad_action(self):
        raise RuntimeError("action failed")


class ErrorInAfterSC(StateChart):
    s1 = State("s1", initial=True)
    s2 = State("s2")
    error_state = State("error_state", final=True)

    go = s1.to(s2, after="bad_after")
    error_execution = Event(s2.to(error_state), id="error.execution")

    def bad_after(self):
        raise RuntimeError("after failed")


class ErrorInGuardSM(StateMachine):
    """StateMachine subclass: exceptions should propagate."""

    initial = State("initial", initial=True)

    go = initial.to(initial, cond="bad_guard") | initial.to(initial)

    def bad_guard(self):
        raise RuntimeError("guard failed")


class ErrorInActionSMWithFlag(StateMachine):
    """StateMachine subclass with error_on_execution = True."""

    error_on_execution = True

    s1 = State("s1", initial=True)
    s2 = State("s2")
    error_state = State("error_state", final=True)

    go = s1.to(s2, on="bad_action")
    error_execution = Event(s1.to(error_state) | s2.to(error_state), id="error.execution")

    def bad_action(self):
        raise RuntimeError("action failed")


class ErrorInErrorHandlerSC(StateChart):
    """Error in error.execution handler should not cause infinite loop."""

    s1 = State("s1", initial=True)
    s2 = State("s2", final=True)

    go = s1.to(s2, on="bad_action")
    error_execution = Event(s1.to(s1, on="bad_error_handler"), id="error.execution")

    def bad_action(self):
        raise RuntimeError("action failed")

    def bad_error_handler(self):
        raise RuntimeError("error handler also failed")


def test_exception_in_guard_sends_error_execution():
    """Exception in guard returns False and sends error.execution event."""
    sm = ErrorInGuardSC()
    assert sm.configuration == {sm.initial}

    sm.send("go")

    # The bad_guard raises, so error.execution is sent, transitioning to error_state
    assert sm.configuration == {sm.error_state}


def test_exception_in_on_enter_sends_error_execution():
    """Exception in on_enter sends error.execution and rolls back configuration."""
    sm = ErrorInOnEnterSC()
    assert sm.configuration == {sm.s1}

    sm.send("go")

    # on_enter_s2 raises, config is rolled back to s1, then error.execution fires
    assert sm.configuration == {sm.error_state}


def test_exception_in_action_sends_error_execution():
    """Exception in transition 'on' action sends error.execution."""
    sm = ErrorInActionSC()
    assert sm.configuration == {sm.s1}

    sm.send("go")

    # bad_action raises during transition, config rolls back to s1,
    # then error.execution fires
    assert sm.configuration == {sm.error_state}


def test_exception_in_after_sends_error_execution_no_rollback():
    """Exception in 'after' action sends error.execution but does NOT roll back."""
    sm = ErrorInAfterSC()
    assert sm.configuration == {sm.s1}

    sm.send("go")

    # Transition s1->s2 completes, then bad_after raises,
    # error.execution fires from s2 -> error_state
    assert sm.configuration == {sm.error_state}


def test_statemachine_exception_propagates():
    """StateMachine (error_on_execution=False) should propagate exceptions normally."""
    sm = ErrorInGuardSM()
    assert sm.configuration == {sm.initial}

    # The bad_guard raises RuntimeError, which should propagate
    with pytest.raises(RuntimeError, match="guard failed"):
        sm.send("go")


def test_invalid_definition_always_propagates():
    """InvalidDefinition should always propagate regardless of error_on_execution."""

    class BadDefinitionSC(StateChart):
        s1 = State("s1", initial=True)
        s2 = State("s2", final=True)

        go = s1.to(s2, cond="bad_cond")

        def bad_cond(self):
            raise InvalidDefinition("bad definition")

    sm = BadDefinitionSC()
    with pytest.raises(InvalidDefinition, match="bad definition"):
        sm.send("go")


def test_error_in_error_handler_no_infinite_loop():
    """Error while processing error.execution should not cause infinite loop."""
    sm = ErrorInErrorHandlerSC()
    assert sm.configuration == {sm.s1}

    # bad_action raises -> error.execution fires -> bad_error_handler raises
    # Second error during error.execution processing is ignored (logged as warning)
    sm.send("go")

    # Machine should still be in s1 (rolled back from failed transition)
    assert sm.configuration == {sm.s1}


def test_statemachine_with_error_on_execution_true():
    """Custom StateMachine subclass with error_on_execution=True should catch errors."""
    sm = ErrorInActionSMWithFlag()
    assert sm.configuration == {sm.s1}

    sm.send("go")

    assert sm.configuration == {sm.error_state}


def test_error_data_available_in_error_execution_handler():
    """The error object should be available in the error.execution event kwargs."""
    received_errors = []

    class ErrorDataSC(StateChart):
        s1 = State("s1", initial=True)
        error_state = State("error_state", final=True)

        go = s1.to(s1, on="bad_action")
        error_execution = Event(s1.to(error_state, on="handle_error"), id="error.execution")

        def bad_action(self):
            raise RuntimeError("specific error message")

        def handle_error(self, error=None, **kwargs):
            received_errors.append(error)

    sm = ErrorDataSC()
    sm.send("go")

    assert sm.configuration == {sm.error_state}
    assert len(received_errors) == 1
    assert isinstance(received_errors[0], RuntimeError)
    assert str(received_errors[0]) == "specific error message"
