import re

import pytest
from statemachine.exceptions import InvalidDefinition
from statemachine.exceptions import InvalidStateValue

from statemachine import State
from statemachine import StateChart
from statemachine import StateMachine


@pytest.fixture()
def async_order_control_machine():  # noqa: C901
    class OrderControl(StateMachine):
        waiting_for_payment = State(initial=True)
        processing = State()
        shipping = State()
        completed = State(final=True)

        add_to_order = waiting_for_payment.to(waiting_for_payment)
        receive_payment = waiting_for_payment.to(
            processing, cond="payments_enough"
        ) | waiting_for_payment.to(waiting_for_payment, unless="payments_enough")
        process_order = processing.to(shipping, cond="payment_received")
        ship_order = shipping.to(completed)

        def __init__(self):
            self.order_total = 0
            self.payments = []
            self.payment_received = False
            super().__init__()

        async def payments_enough(self, amount):
            return sum(self.payments) + amount >= self.order_total

        async def before_add_to_order(self, amount):
            self.order_total += amount
            return self.order_total

        async def before_receive_payment(self, amount):
            self.payments.append(amount)
            return self.payments

        async def after_receive_payment(self):
            self.payment_received = True

        async def on_enter_waiting_for_payment(self):
            self.payment_received = False

    return OrderControl


async def test_async_order_control_machine(async_order_control_machine):
    sm = async_order_control_machine()

    assert await sm.add_to_order(3) == 3
    assert await sm.add_to_order(7) == 10

    assert await sm.receive_payment(4) == [4]
    assert sm.waiting_for_payment.is_active

    with pytest.raises(sm.TransitionNotAllowed):
        await sm.process_order()

    assert sm.waiting_for_payment.is_active

    assert await sm.receive_payment(6) == [4, 6]
    await sm.process_order()

    await sm.ship_order()
    assert sm.order_total == 10
    assert sm.payments == [4, 6]
    assert sm.completed.is_active


def test_async_state_from_sync_context(async_order_control_machine):
    """Test that an async state machine can be used from a synchronous context"""

    sm = async_order_control_machine()

    assert sm.add_to_order(3) == 3
    assert sm.add_to_order(7) == 10

    assert sm.receive_payment(4) == [4]
    assert sm.waiting_for_payment.is_active

    with pytest.raises(sm.TransitionNotAllowed):
        sm.process_order()

    assert sm.waiting_for_payment.is_active

    assert sm.send("receive_payment", 6) == [4, 6]  # test the sync version of the `.send()` method
    sm.send("process_order")  # test the sync version of the `.send()` method

    sm.ship_order()
    assert sm.order_total == 10
    assert sm.payments == [4, 6]
    assert sm.completed.is_active


class AsyncConditionExpressionMachine(StateMachine):
    """Regression test for issue #535: async conditions in boolean expressions."""

    s1 = State(initial=True)

    go_not = s1.to.itself(cond="not cond_false")
    go_and = s1.to.itself(cond="cond_true and cond_true")
    go_or_false_first = s1.to.itself(cond="cond_false or cond_true")
    go_or_true_first = s1.to.itself(cond="cond_true or cond_false")
    go_blocked = s1.to.itself(cond="not cond_true")
    go_and_blocked = s1.to.itself(cond="cond_true and cond_false")
    go_or_both_false = s1.to.itself(cond="cond_false or cond_false")

    async def cond_true(self):
        return True

    async def cond_false(self):
        return False

    async def on_enter_state(self, target):
        """Async callback to ensure the SM uses AsyncEngine."""


async def test_async_condition_not(recwarn):
    """Issue #535: 'not cond_false' should allow the transition."""
    sm = AsyncConditionExpressionMachine()
    await sm.activate_initial_state()
    await sm.go_not()
    assert sm.s1.is_active
    assert not any("coroutine" in str(w.message) for w in recwarn.list)


async def test_async_condition_not_blocked():
    """Issue #535: 'not cond_true' should block the transition."""
    sm = AsyncConditionExpressionMachine()
    await sm.activate_initial_state()
    with pytest.raises(sm.TransitionNotAllowed):
        await sm.go_blocked()


async def test_async_condition_and():
    """Issue #535: 'cond_true and cond_true' should allow the transition."""
    sm = AsyncConditionExpressionMachine()
    await sm.activate_initial_state()
    await sm.go_and()
    assert sm.s1.is_active


async def test_async_condition_and_blocked():
    """Issue #535: 'cond_true and cond_false' should block the transition."""
    sm = AsyncConditionExpressionMachine()
    await sm.activate_initial_state()
    with pytest.raises(sm.TransitionNotAllowed):
        await sm.go_and_blocked()


async def test_async_condition_or_false_first():
    """Issue #535: 'cond_false or cond_true' should allow the transition."""
    sm = AsyncConditionExpressionMachine()
    await sm.activate_initial_state()
    await sm.go_or_false_first()
    assert sm.s1.is_active


async def test_async_condition_or_true_first():
    """'cond_true or cond_false' should allow the transition."""
    sm = AsyncConditionExpressionMachine()
    await sm.activate_initial_state()
    await sm.go_or_true_first()
    assert sm.s1.is_active


async def test_async_condition_or_both_false():
    """'cond_false or cond_false' should block the transition."""
    sm = AsyncConditionExpressionMachine()
    await sm.activate_initial_state()
    with pytest.raises(sm.TransitionNotAllowed):
        await sm.go_or_both_false()


async def test_async_state_should_be_initialized(async_order_control_machine):
    """Test that the state machine is initialized before any event is triggered

    Given how async works on python, there's no built-in way to activate the initial state that
    may depend on async code from the StateMachine.__init__ method.

    We do a `_ensure_is_initialized()` check before each event, but to check the current state
    just before the state machine is created, the user must await the activation of the initial
    state explicitly.
    """

    sm = async_order_control_machine()
    with pytest.raises(
        InvalidStateValue,
        match=re.escape(
            r"There's no current state set. In async code, "
            r"did you activate the initial state? (e.g., `await sm.activate_initial_state()`)"
        ),
    ):
        assert sm.current_state == sm.waiting_for_payment

    await sm.activate_initial_state()
    assert sm.current_state == sm.waiting_for_payment


@pytest.mark.timeout(5)
async def test_async_error_on_execution_in_condition():
    """Async engine catches errors in conditions with error_on_execution."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State()
        error_state = State(final=True)

        go = s1.to(s2, cond="bad_cond")
        error_execution = s1.to(error_state)

        def bad_cond(self, **kwargs):
            raise RuntimeError("Condition boom")

    sm = SM()
    sm.send("go")
    assert sm.configuration == {sm.error_state}


@pytest.mark.timeout(5)
async def test_async_error_on_execution_in_transition():
    """Async engine catches errors in transition callbacks with error_on_execution."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State()
        error_state = State(final=True)

        go = s1.to(s2, on="bad_action")
        error_execution = s1.to(error_state)

        def bad_action(self, **kwargs):
            raise RuntimeError("Transition boom")

    sm = SM()
    sm.send("go")
    assert sm.configuration == {sm.error_state}


@pytest.mark.timeout(5)
async def test_async_error_on_execution_in_after():
    """Async engine catches errors in after callbacks with error_on_execution."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State()
        error_state = State(final=True)

        go = s1.to(s2)
        error_execution = s2.to(error_state)

        def after_go(self, **kwargs):
            raise RuntimeError("After boom")

    sm = SM()
    sm.send("go")
    assert sm.configuration == {sm.error_state}


@pytest.mark.timeout(5)
async def test_async_invalid_definition_in_transition_propagates():
    """InvalidDefinition in async transition propagates."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State()

        go = s1.to(s2, on="bad_action")

        def bad_action(self, **kwargs):
            raise InvalidDefinition("Bad async")

    sm = SM()
    with pytest.raises(InvalidDefinition, match="Bad async"):
        sm.send("go")


@pytest.mark.timeout(5)
async def test_async_invalid_definition_in_after_propagates():
    """InvalidDefinition in async after callback propagates."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State(final=True)

        go = s1.to(s2)

        def after_go(self, **kwargs):
            raise InvalidDefinition("Bad async after")

    sm = SM()
    with pytest.raises(InvalidDefinition, match="Bad async after"):
        sm.send("go")


@pytest.mark.timeout(5)
async def test_async_runtime_error_in_after_without_error_on_execution():
    """RuntimeError in async after callback without error_on_execution propagates."""

    class SM(StateMachine):
        s1 = State(initial=True)
        s2 = State(final=True)

        go = s1.to(s2)

        def after_go(self, **kwargs):
            raise RuntimeError("Async after boom")

    sm = SM()
    with pytest.raises(RuntimeError, match="Async after boom"):
        sm.send("go")


# --- Actual async engine tests (async callbacks trigger AsyncEngine) ---
# Note: async engine error_on_execution with async callbacks has a known limitation:
# _send_error_execution calls sm.send() which returns an unawaited coroutine.
# The tests below cover the paths that DO work in the async engine.


@pytest.mark.timeout(5)
async def test_async_engine_invalid_definition_in_condition_propagates():
    """AsyncEngine: InvalidDefinition in async condition always propagates."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State()

        go = s1.to(s2, cond="bad_cond")

        async def bad_cond(self, **kwargs):
            raise InvalidDefinition("Async bad definition")

    sm = SM()
    await sm.activate_initial_state()
    with pytest.raises(InvalidDefinition, match="Async bad definition"):
        await sm.send("go")


@pytest.mark.timeout(5)
async def test_async_engine_invalid_definition_in_transition_propagates():
    """AsyncEngine: InvalidDefinition in async transition execution always propagates."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State()

        go = s1.to(s2, on="bad_action")

        async def bad_action(self, **kwargs):
            raise InvalidDefinition("Async bad transition")

    sm = SM()
    await sm.activate_initial_state()
    with pytest.raises(InvalidDefinition, match="Async bad transition"):
        await sm.send("go")


@pytest.mark.timeout(5)
async def test_async_engine_invalid_definition_in_after_propagates():
    """AsyncEngine: InvalidDefinition in async after callback propagates."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State(final=True)

        go = s1.to(s2)

        async def after_go(self, **kwargs):
            raise InvalidDefinition("Async bad after")

    sm = SM()
    await sm.activate_initial_state()
    with pytest.raises(InvalidDefinition, match="Async bad after"):
        await sm.send("go")


@pytest.mark.timeout(5)
async def test_async_engine_runtime_error_in_after_without_error_on_execution_propagates():
    """AsyncEngine: RuntimeError in async after callback without error_on_execution raises."""

    class SM(StateMachine):
        s1 = State(initial=True)
        s2 = State(final=True)

        go = s1.to(s2)

        async def after_go(self, **kwargs):
            raise RuntimeError("Async after boom no catch")

    sm = SM()
    await sm.activate_initial_state()
    with pytest.raises(RuntimeError, match="Async after boom no catch"):
        await sm.send("go")


@pytest.mark.timeout(5)
async def test_async_engine_start_noop_when_already_initialized():
    """BaseEngine.start() is a no-op when state machine is already initialized."""

    class SM(StateMachine):
        s1 = State(initial=True)
        s2 = State(final=True)

        go = s1.to(s2)

        async def on_go(
            self,
        ): ...  # No-op: presence of async callback triggers AsyncEngine selection

    sm = SM()
    await sm.activate_initial_state()
    assert sm.current_state_value is not None
    sm._engine.start()  # Should return early
    assert sm.s1.is_active


class TestAsyncEnabledEvents:
    async def test_passing_async_condition(self):
        class MyMachine(StateMachine):
            s0 = State(initial=True)
            s1 = State(final=True)

            go = s0.to(s1, cond="is_ready")

            async def is_ready(self):
                return True

        sm = MyMachine()
        await sm.activate_initial_state()
        assert [e.id for e in await sm.enabled_events()] == ["go"]

    async def test_failing_async_condition(self):
        class MyMachine(StateMachine):
            s0 = State(initial=True)
            s1 = State(final=True)

            go = s0.to(s1, cond="is_ready")

            async def is_ready(self):
                return False

        sm = MyMachine()
        await sm.activate_initial_state()
        assert await sm.enabled_events() == []

    async def test_kwargs_forwarded_to_async_conditions(self):
        class MyMachine(StateMachine):
            s0 = State(initial=True)
            s1 = State(final=True)

            go = s0.to(s1, cond="check_value")

            async def check_value(self, value=0):
                return value > 10

        sm = MyMachine()
        await sm.activate_initial_state()
        assert await sm.enabled_events() == []
        assert [e.id for e in await sm.enabled_events(value=20)] == ["go"]

    async def test_async_condition_exception_treated_as_enabled(self):
        class MyMachine(StateMachine):
            s0 = State(initial=True)
            s1 = State(final=True)

            go = s0.to(s1, cond="bad_cond")

            async def bad_cond(self):
                raise RuntimeError("boom")

        sm = MyMachine()
        await sm.activate_initial_state()
        assert [e.id for e in await sm.enabled_events()] == ["go"]

    async def test_mixed_enabled_and_disabled_async(self):
        class MyMachine(StateMachine):
            s0 = State(initial=True)
            s1 = State()
            s2 = State(final=True)

            go = s0.to(s1, cond="cond_true")
            stop = s0.to(s2, cond="cond_false")

            async def cond_true(self):
                return True

            async def cond_false(self):
                return False

        sm = MyMachine()
        await sm.activate_initial_state()
        assert [e.id for e in await sm.enabled_events()] == ["go"]
