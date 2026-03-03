"""Tests for the validators feature.

Validators are imperative guards that raise exceptions to reject transitions.
Unlike conditions (cond/unless), which return booleans and silently skip
transitions, validators communicate *why* a transition was rejected.

Key behavior (since v3): validator exceptions always propagate to the caller,
regardless of the ``catch_errors_as_events`` flag. They are NOT converted to
``error.execution`` events — they operate in the transition-selection phase,
not the execution phase.
"""

import pytest

from tests.machines.validators.multi_validator import MultiValidator
from tests.machines.validators.order_validation import OrderValidation
from tests.machines.validators.order_validation_no_error_events import OrderValidationNoErrorEvents
from tests.machines.validators.validator_fallthrough import ValidatorFallthrough
from tests.machines.validators.validator_with_cond import ValidatorWithCond
from tests.machines.validators.validator_with_error_transition import ValidatorWithErrorTransition


class TestValidatorPropagation:
    """Validator exceptions always propagate to the caller."""

    async def test_validator_rejects_with_catch_errors_as_events_true(self, sm_runner):
        """With catch_errors_as_events=True (default), validator exceptions still
        propagate — they are NOT converted to error.execution events."""
        sm = await sm_runner.start(OrderValidation)

        with pytest.raises(ValueError, match="Quantity must be positive"):
            await sm_runner.send(sm, "confirm", quantity=0)

        assert "pending" in sm.configuration_values

    async def test_validator_rejects_with_catch_errors_as_events_false(self, sm_runner):
        """With catch_errors_as_events=False, validator exceptions propagate
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

    Even when catch_errors_as_events=True and an error.execution transition
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
