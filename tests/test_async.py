import re

import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.exceptions import InvalidStateValue


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
