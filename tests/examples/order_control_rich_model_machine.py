"""
Order control machine (rich model)
==================================

An StateMachine that demonstrates :ref:`Actions` being used on a rich model.

"""
from statemachine import State
from statemachine import StateMachine
from statemachine.exceptions import AttrNotFound


class Order(object):
    def __init__(self):
        self.order_total = 0
        self.payments = []
        self.payment_received = False

    def payments_enough(self, amount):
        return sum(self.payments) + amount >= self.order_total

    def add_to_order(self, amount):
        self.order_total += amount
        return self.order_total

    def on_receive_payment(self, amount):
        self.payments.append(amount)
        return self.payments

    def after_receive_payment(self):
        self.payment_received = True

    def wait_for_payment(self):
        self.payment_received = False


class OrderControl(StateMachine):
    waiting_for_payment = State(
        "Waiting for payment", initial=True, enter="wait_for_payment"
    )
    processing = State("Processing")
    shipping = State("Shipping")
    completed = State("Completed", final=True)

    add_to_order = waiting_for_payment.to(waiting_for_payment, before="add_to_order")
    receive_payment = waiting_for_payment.to(
        processing, cond="payments_enough"
    ) | waiting_for_payment.to(waiting_for_payment, unless="payments_enough")
    process_order = processing.to(shipping, cond="payment_received")
    ship_order = shipping.to(completed)


# %%
# Testing
# -------
#
# Let's first try to create a statemachine instance, using the default dummy model that don't have
# the needed methods to complete the state machine. Since the required methods will not be found
# either in the state machine or in the model, an exception ``AttrNotFound`` will be raised.

try:
    control = OrderControl()
except AttrNotFound as e:
    assert str(e) == "Did not found name 'payment_received' from model or statemachine"

# %%
# Now initializing with a proper ``order`` instance.

order = Order()
control = OrderControl(order)

# %%
# Send events to add to order

assert control.send("add_to_order", 3) == 3
assert control.send("add_to_order", 7) == 10

# %%
# Receive a payment of $4...

control.send("receive_payment", 4)

# %%
# Since there's still $6 left to fulfill the payment, we cannot process the order.
try:
    control.send("process_order")
except StateMachine.TransitionNotAllowed as err:
    print(err)

# %%

control

# %%
# Now paying the left amount, we can proceed.

control.send("receive_payment", 6)

# %%

control

# %%

control.send("process_order")

# %%

control

# %%

control.send("ship_order")

# %%
# Just checking the final expected state

order.order_total

# %%

order.payments

# %%

control.completed.is_active

# %%

control


# %%
assert order.order_total == 10
assert order.payments == [4, 6]
assert control.completed.is_active
