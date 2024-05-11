"""
Order control machine
---------------------

An StateMachine that demonstrates :ref:`Guards` being used to control the state flow.

"""

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
