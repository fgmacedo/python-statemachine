import weakref

import pytest

from statemachine import State
from statemachine import StateMachine


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


class Order:
    def __init__(self):
        self.order_total = 0
        self.payments = []
        self.payment_received = False
        self.state_machine = OrderControl(model=weakref.proxy(self))

    def payments_enough(self, amount):
        return sum(self.payments) + amount >= self.order_total

    def before_add_to_order(self, amount):
        self.order_total += amount
        return self.order_total

    def on_receive_payment(self, amount):
        self.payments.append(amount)
        return self.payments

    def after_receive_payment(self):
        self.payment_received = True


def create_order():
    order = Order()
    assert order.state_machine.waiting_for_payment.is_active


def add_to_order(sm, amount):
    sm.add_to_order(amount)


@pytest.mark.slow()
def test_setup_performance(benchmark):
    benchmark.pedantic(create_order, rounds=10, iterations=1000)


@pytest.mark.slow()
def test_event_performance(benchmark):
    order = Order()
    benchmark.pedantic(add_to_order, args=(order.state_machine, 1), rounds=10, iterations=1000)
