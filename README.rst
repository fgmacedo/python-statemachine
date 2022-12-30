====================
Python State Machine
====================


.. image:: https://img.shields.io/pypi/v/python-statemachine.svg
        :target: https://pypi.python.org/pypi/python-statemachine

.. image:: https://img.shields.io/pypi/dm/python-statemachine.svg
        :target: https://pypi.python.org/pypi/python-statemachine

.. image:: https://travis-ci.org/fgmacedo/python-statemachine.svg?branch=develop
        :target: https://travis-ci.org/fgmacedo/python-statemachine
        :alt: Build status

.. image:: https://codecov.io/gh/fgmacedo/python-statemachine/branch/develop/graph/badge.svg
        :target: https://codecov.io/gh/fgmacedo/python-statemachine
        :alt: Coverage report

.. image:: https://readthedocs.org/projects/python-statemachine/badge/?version=latest
        :target: https://python-statemachine.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://img.shields.io/github/commits-since/fgmacedo/python-statemachine/main/develop
   :alt: GitHub commits since last release (main)


Python `finite-state machines <https://en.wikipedia.org/wiki/Finite-state_machine>`_ made easy.


* Free software: MIT license
* Documentation: https://python-statemachine.readthedocs.io.


Welcome to python-statemachine, an intuitive and powerful state machine framework designed for a
great developer experience.

🚀 With StateMachine, you can easily create complex, dynamic systems with clean, readable code.

💡 Our framework makes it easy to understand and reason about the different states, events and
transitions in your system, so you can focus on building great products.

🔒 python-statemachine also provides robust error handling and ensures that your system stays
in a valid state at all times.


A few reasons why you may consider using it:

* 📈 python-statemachine is designed to help you build scalable,
  maintainable systems that can handle any complexity.
* 💪 You can easily create and manage multiple state machines within a single application.
* 🚫 Prevents common mistakes and ensures that your system stays in a valid state at all times.


Getting started
===============

To install Python State Machine, run this command in your terminal:

.. code-block:: console

    $ pip install python-statemachine

Define your state machine:

>>> from statemachine import StateMachine, State

>>> class TrafficLightMachine(StateMachine):
...     "A traffic light machine"
...     green = State("Green", initial=True)
...     yellow = State("Yellow")
...     red = State("Red")
...
...     cycle = green.to(yellow) | yellow.to(red) | red.to(green)
...
...     slowdown = green.to(yellow)
...     stop = yellow.to(red)
...     go = red.to(green)
...
...     def before_cycle(self, event_data=None):
...         message = event_data.kwargs.get("message", "")
...         message = ". " + message if message else ""
...         return "Running {} from {} to {}{}".format(
...             event_data.event.name,
...             event_data.transition.source.identifier,
...             event_data.transition.destination.identifier,
...             message,
...         )
...
...     def on_enter_red(self):
...         print("Don't move.")
...
...     def on_exit_red(self):
...         print("Go ahead!")


You can now create an instance:

>>> traffic_light = TrafficLightMachine()

Them start sending events:

>>> traffic_light.cycle()
'Running cycle from green to yellow'

You can inspect about the current state:

>>> traffic_light.current_state.identifier
'yellow'

Or get a complete state repr for debugging purposes:

>>> traffic_light.current_state
State('Yellow', identifier='yellow', value='yellow', initial=False, final=False)

The ``State`` instance can also be checked by equality:

>>> traffic_light.current_state == TrafficLightMachine.yellow
True

>>> traffic_light.current_state == traffic_light.yellow
True

But for your convenience, a dynamically property ``is_<state.identifier>`` is created for each state,
so you can easily check if a machine is at a specific state at any time:

>>> traffic_light.is_green
False

>>> traffic_light.is_yellow
True

>>> traffic_light.is_red
False

Easily iterate over all states:

>>> [s.identifier for s in traffic_light.states]
['green', 'red', 'yellow']

Or over events:

>>> [t.name for t in traffic_light.events]
['cycle', 'go', 'slowdown', 'stop']

Call an event by it's name:

>>> traffic_light.cycle()
Don't move.
'Running cycle from yellow to red'

Or sending an trigger with the event name:

>>> traffic_light.run('cycle')
Go ahead!
'Running cycle from red to green'

>>> traffic_light.is_green
True

You can't run a transition from an invalid state:

>>> traffic_light.go()
Traceback (most recent call last):
statemachine.exceptions.TransitionNotAllowed: Can't go when in Green.

Keeping the same state as expected:

>>> traffic_light.is_green
True

And you can pass arbitrary positional or keyword arguments to the event, and
they will be propagated to all actions and callbacks:

>>> traffic_light.cycle(message="Please, now slowdon.")
'Running cycle from green to yellow. Please, now slowdon.'


Models
------

If you need to persist the current state on another object, or you're using the
state machine to control the flow of another object, you can pass this object
to the ``StateMachine`` constructor:

>>> class MyModel(object):
...     def __init__(self, state):
...         self.state = state
...

>>> obj = MyModel(state='red')

>>> traffic_light = TrafficLightMachine(obj)

>>> traffic_light.is_red
True

>>> obj.state
'red'

>>> obj.state = 'green'

>>> traffic_light.is_green
True

>>> traffic_light.slowdown()

>>> obj.state
'yellow'

>>> traffic_light.is_yellow
True


A more useful example
---------------------

A simple didactic state machine for controlling an ``Order``:


>>> class OrderControl(StateMachine):  # type: ignore
...     waiting_for_payment = State("Waiting for payment", initial=True)
...     processing = State("Processing")
...     shipping = State("Shipping")
...     completed = State("Completed", final=True)
...
...     add_to_order = waiting_for_payment.to(waiting_for_payment)
...     receive_payment = (
...         waiting_for_payment.to(processing, conditions="payments_enough")
...         | waiting_for_payment.to(waiting_for_payment, unless="payments_enough")
...     )
...     process_order = processing.to(shipping, conditions="payment_received")
...     ship_order = shipping.to(completed)
...
...     def __init__(self):
...         self.order_total = 0
...         self.payments = []
...         self.payment_received = False
...         super(OrderControl, self).__init__()
...
...     def payments_enough(self, amount):
...         return sum(self.payments) + amount >= self.order_total
...
...     def before_add_to_order(self, amount):
...         self.order_total += amount
...         return self.order_total
...
...     def before_receive_payment(self, amount):
...         self.payments.append(amount)
...         return self.payments
...
...     def after_receive_payment(self):
...         self.payment_received = True
...
...     def on_enter_waiting_for_payment(self):
...         self.payment_received = False



You can use this machine as follows.

>>> control = OrderControl()

>>> control.add_to_order(3)
3

>>> control.add_to_order(7)
10

>>> control.receive_payment(4)
[4]

>>> control.current_state.identifier
'waiting_for_payment'

>>> control.process_order()
Traceback (most recent call last):
...
statemachine.exceptions.TransitionNotAllowed: Can't process_order when in Waiting for payment.

>>> control.receive_payment(6)
[4, 6]

>>> control.current_state.identifier
'processing'

>>> control.process_order()

>>> control.ship_order()

>>> control.payment_received
True

>>> control.order_total
10

>>> control.payments
[4, 6]

>>> control.is_completed
True

