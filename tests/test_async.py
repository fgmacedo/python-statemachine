import pytest

from statemachine import State
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

    return OrderControl()


async def test_async_order_control_machine(async_order_control_machine):
    sm = async_order_control_machine

    assert await sm.async_add_to_order(3) == 3
    assert await sm.async_add_to_order(7) == 10

    assert await sm.async_receive_payment(4) == [4]
    assert sm.waiting_for_payment.is_active

    with pytest.raises(sm.TransitionNotAllowed):
        await sm.async_process_order()

    assert sm.waiting_for_payment.is_active

    assert await sm.async_receive_payment(6) == [4, 6]
    await sm.async_process_order()

    await sm.async_ship_order()
    assert sm.order_total == 10
    assert sm.payments == [4, 6]
    assert sm.completed.is_active
