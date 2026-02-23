"""Tests for the validators feature.

Validators are imperative guards that raise exceptions to reject transitions.
Unlike conditions (cond/unless), which return booleans and silently skip
transitions, validators communicate *why* a transition was rejected.

Key behavior (since v3): validator exceptions always propagate to the caller,
regardless of the ``error_on_execution`` flag. They are NOT converted to
``error.execution`` events — they operate in the transition-selection phase,
not the execution phase.
"""

import pytest

from statemachine import State
from statemachine import StateChart

# ---------------------------------------------------------------------------
# State machine definitions used across tests
# ---------------------------------------------------------------------------


class OrderValidation(StateChart):
    """StateChart with error_on_execution=True (the default)."""

    pending = State(initial=True)
    confirmed = State()
    cancelled = State(final=True)

    confirm = pending.to(confirmed, validators="check_stock")
    cancel = confirmed.to(cancelled)

    def check_stock(self, quantity=0, **kwargs):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")


class OrderValidationNoErrorEvents(StateChart):
    """Same machine but with error_on_execution=False."""

    error_on_execution = False

    pending = State(initial=True)
    confirmed = State()
    cancelled = State(final=True)

    confirm = pending.to(confirmed, validators="check_stock")
    cancel = confirmed.to(cancelled)

    def check_stock(self, quantity=0, **kwargs):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")


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


class ValidatorWithCond(StateChart):
    """Machine that combines validators and conditions on the same transition."""

    idle = State(initial=True)
    active = State(final=True)

    start = idle.to(active, validators="check_auth", cond="has_permission")

    has_permission = False

    def check_auth(self, token=None, **kwargs):
        if token != "valid":
            raise PermissionError("Invalid token")


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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidatorPropagation:
    """Validator exceptions always propagate to the caller."""

    async def test_validator_rejects_with_error_on_execution_true(self, sm_runner):
        """With error_on_execution=True (default), validator exceptions still
        propagate — they are NOT converted to error.execution events."""
        sm = await sm_runner.start(OrderValidation)

        with pytest.raises(ValueError, match="Quantity must be positive"):
            await sm_runner.send(sm, "confirm", quantity=0)

        assert "pending" in sm.configuration_values

    async def test_validator_rejects_with_error_on_execution_false(self, sm_runner):
        """With error_on_execution=False, validator exceptions propagate
        (same behavior as True — validators always propagate)."""
        sm = await sm_runner.start(OrderValidationNoErrorEvents)

        with pytest.raises(ValueError, match="Quantity must be positive"):
            await sm_runner.send(sm, "confirm", quantity=0)

        assert "pending" in sm.configuration_values

    async def test_validator_accepts(self, sm_runner):
        """When the validator passes, the transition proceeds normally."""
        sm = await sm_runner.start(OrderValidation)
        await sm_runner.send(sm, "confirm", quantity=5)
        assert "confirmed" in sm.configuration_values

    async def test_state_unchanged_after_rejection(self, sm_runner):
        """After a validator rejects, the machine stays in the source state
        and can still process events normally."""
        sm = await sm_runner.start(OrderValidation)

        with pytest.raises(ValueError, match="Quantity must be positive"):
            await sm_runner.send(sm, "confirm", quantity=0)

        # Machine is still in pending — retry with valid data
        await sm_runner.send(sm, "confirm", quantity=10)
        assert "confirmed" in sm.configuration_values


class TestMultipleValidators:
    """When multiple validators are declared, they run in order."""

    async def test_first_validator_fails(self, sm_runner):
        """First validator failure stops the chain — second is not called."""
        sm = await sm_runner.start(MultiValidator)

        with pytest.raises(ValueError, match="A failed"):
            await sm_runner.send(sm, "start", a_ok=False, b_ok=True)

        assert "idle" in sm.configuration_values

    async def test_second_validator_fails(self, sm_runner):
        """First passes, second fails."""
        sm = await sm_runner.start(MultiValidator)

        with pytest.raises(ValueError, match="B failed"):
            await sm_runner.send(sm, "start", a_ok=True, b_ok=False)

        assert "idle" in sm.configuration_values

    async def test_all_validators_pass(self, sm_runner):
        sm = await sm_runner.start(MultiValidator)
        await sm_runner.send(sm, "start", a_ok=True, b_ok=True)
        assert "active" in sm.configuration_values


class TestValidatorWithConditions:
    """Validators and conditions can be combined on the same transition.
    Validators run first (see execution order in actions.md)."""

    async def test_validator_rejects_before_cond_is_evaluated(self, sm_runner):
        """Validator runs before cond — if it rejects, cond is never checked."""
        sm = await sm_runner.start(ValidatorWithCond)
        sm.has_permission = True  # cond would pass

        with pytest.raises(PermissionError, match="Invalid token"):
            await sm_runner.send(sm, "start", token="bad")

        assert "idle" in sm.configuration_values

    async def test_validator_passes_but_cond_rejects(self, sm_runner):
        """Validator passes, but cond returns False — no transition, no exception."""
        sm = await sm_runner.start(ValidatorWithCond)
        sm.has_permission = False

        await sm_runner.send(sm, "start", token="valid")
        assert "idle" in sm.configuration_values

    async def test_both_validator_and_cond_pass(self, sm_runner):
        sm = await sm_runner.start(ValidatorWithCond)
        sm.has_permission = True
        await sm_runner.send(sm, "start", token="valid")
        assert "active" in sm.configuration_values


class TestValidatorDoesNotTriggerErrorExecution:
    """The key semantic: validator rejection is NOT an execution error.

    Even when error_on_execution=True and an error.execution transition
    exists, a validator raising should propagate to the caller — not
    be routed through the error.execution mechanism.
    """

    async def test_validator_does_not_trigger_error_transition(self, sm_runner):
        sm = await sm_runner.start(ValidatorWithErrorTransition)

        with pytest.raises(ValueError, match="Input required"):
            await sm_runner.send(sm, "start")

        # Machine stays in idle — NOT in error_state
        assert "idle" in sm.configuration_values

    async def test_action_error_does_trigger_error_transition(self, sm_runner):
        """Contrast: actual action errors DO trigger error.execution."""
        sm = await sm_runner.start(ValidatorWithErrorTransition)

        # First, get to active state (validator passes)
        await sm_runner.send(sm, "start", value="something")
        assert "active" in sm.configuration_values

        # Now trigger an action error — this SHOULD go to error_state
        await sm_runner.send(sm, "do_work")
        assert "error_state" in sm.configuration_values


class TestValidatorFallthrough:
    """When a validator rejects, the exception propagates immediately.
    The engine does NOT try the next transition in the chain."""

    async def test_validator_rejection_does_not_fallthrough(self, sm_runner):
        sm = await sm_runner.start(ValidatorFallthrough)

        with pytest.raises(PermissionError, match="Premium required"):
            await sm_runner.send(sm, "go", premium=False)

        # Machine stays in idle — did NOT fall through to path_b
        assert "idle" in sm.configuration_values

    async def test_validator_passes_takes_first_transition(self, sm_runner):
        sm = await sm_runner.start(ValidatorFallthrough)
        await sm_runner.send(sm, "go", premium=True)
        assert "path_a" in sm.configuration_values
