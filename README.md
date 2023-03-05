# Python StateMachine

[![pypi](https://img.shields.io/pypi/v/python-statemachine.svg)](https://pypi.python.org/pypi/python-statemachine)
[![downloads](https://img.shields.io/pypi/dm/python-statemachine.svg)](https://pypi.python.org/pypi/python-statemachine)
[![build status](https://github.com/fgmacedo/python-statemachine/actions/workflows/python-package.yml/badge.svg?branch=develop)](https://github.com/fgmacedo/python-statemachine/actions/workflows/python-package.yml?query=branch%3Adevelop)
[![Coverage report](https://codecov.io/gh/fgmacedo/python-statemachine/branch/develop/graph/badge.svg)](https://codecov.io/gh/fgmacedo/python-statemachine)
[![Documentation Status](https://readthedocs.org/projects/python-statemachine/badge/?version=latest)](https://python-statemachine.readthedocs.io/en/latest/?badge=latest)
[![GitHub commits since last release (main)](https://img.shields.io/github/commits-since/fgmacedo/python-statemachine/main/develop)](https://github.com/fgmacedo/python-statemachine/compare/main...develop)


Python [finite-state machines](https://en.wikipedia.org/wiki/Finite-state_machine) made easy.


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


## Getting started


To install Python State Machine, run this command in your terminal:

    pip install python-statemachine

To generate diagrams from your machines, you'll also need `pydot` and `Graphviz`. You can
install this library already with `pydot` dependency using the `extras` install option. See
our docs for more details.

    pip install python-statemachine[diagrams]

Define your state machine:

```py
>>> from statemachine import StateMachine, State

>>> class TrafficLightMachine(StateMachine):
...     "A traffic light machine"
...     green = State(initial=True)
...     yellow = State()
...     red = State()
...
...     cycle = green.to(yellow) | yellow.to(red) | red.to(green)
...
...     slowdown = green.to(yellow)
...     stop = yellow.to(red)
...     go = red.to(green)
...
...     def before_cycle(self, event: str, source: State, target: State, message: str = ""):
...         message = ". " + message if message else ""
...         return f"Running {event} from {source.id} to {target.id}{message}"
...
...     def on_enter_red(self):
...         print("Don't move.")
...
...     def on_exit_red(self):
...         print("Go ahead!")

```

You can now create an instance:

```py
>>> traffic_light = TrafficLightMachine()

```

Then start sending events:

```py
>>> traffic_light.cycle()
'Running cycle from green to yellow'

```

You can inspect the current state:

```py
>>> traffic_light.current_state.id
'yellow'

```

A `State` human-readable name is automatically derived from the `State.id`:

```py
>>> traffic_light.current_state.name
'Yellow'

```

Or get a complete state representation for debugging purposes:

```py
>>> traffic_light.current_state
State('Yellow', id='yellow', value='yellow', initial=False, final=False)

```

The ``State`` instance can also be checked by equality:

```py
>>> traffic_light.current_state == TrafficLightMachine.yellow
True

>>> traffic_light.current_state == traffic_light.yellow
True

```

But for your convenience, can easily ask if a state is active at any time:

```py
>>> traffic_light.green.is_active
False

>>> traffic_light.yellow.is_active
True

>>> traffic_light.red.is_active
False

```

Easily iterate over all states:

```py
>>> [s.id for s in traffic_light.states]
['green', 'red', 'yellow']

```

Or over events:

```py
>>> [t.name for t in traffic_light.events]
['cycle', 'go', 'slowdown', 'stop']

```

Call an event by its name:

```py
>>> traffic_light.cycle()
Don't move.
'Running cycle from yellow to red'

```
Or send an event with the event name:

```py
>>> traffic_light.send('cycle')
Go ahead!
'Running cycle from red to green'

>>> traffic_light.green.is_active
True

```
You can't run a transition from an invalid state:

```py
>>> traffic_light.go()
Traceback (most recent call last):
statemachine.exceptions.TransitionNotAllowed: Can't go when in Green.

```
Keeping the same state as expected:

```py
>>> traffic_light.green.is_active
True

```

And you can pass arbitrary positional or keyword arguments to the event, and
they will be propagated to all actions and callbacks:

```py
>>> traffic_light.cycle(message="Please, now slowdown.")
'Running cycle from green to yellow. Please, now slowdown.'

```

## A more useful example

A simple didactic state machine for controlling an `Order`:

```py
>>> class OrderControl(StateMachine):
...     waiting_for_payment = State(initial=True)
...     processing = State()
...     shipping = State()
...     completed = State(final=True)
...
...     add_to_order = waiting_for_payment.to(waiting_for_payment)
...     receive_payment = (
...         waiting_for_payment.to(processing, cond="payments_enough")
...         | waiting_for_payment.to(waiting_for_payment, unless="payments_enough")
...     )
...     process_order = processing.to(shipping, cond="payment_received")
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

```

You can use this machine as follows.

```py
>>> control = OrderControl()

>>> control.add_to_order(3)
3

>>> control.add_to_order(7)
10

>>> control.receive_payment(4)
[4]

>>> control.current_state.id
'waiting_for_payment'

>>> control.current_state.name
'Waiting for payment'

>>> control.process_order()
Traceback (most recent call last):
...
statemachine.exceptions.TransitionNotAllowed: Can't process_order when in Waiting for payment.

>>> control.receive_payment(6)
[4, 6]

>>> control.current_state.id
'processing'

>>> control.process_order()

>>> control.ship_order()

>>> control.payment_received
True

>>> control.order_total
10

>>> control.payments
[4, 6]

>>> control.completed.is_active
True

```

There's a lot more to cover, please take a look at our docs:
https://python-statemachine.readthedocs.io.


## Contributing to the project

* <a class="github-button" href="https://github.com/fgmacedo/python-statemachine" data-icon="octicon-star" aria-label="Star fgmacedo/python-statemachine on GitHub">Star this project</a>
* <a class="github-button" href="https://github.com/fgmacedo/python-statemachine/issues" data-icon="octicon-issue-opened" aria-label="Issue fgmacedo/python-statemachine on GitHub">Open an Issue</a>
* <a class="github-button" href="https://github.com/fgmacedo/python-statemachine/fork" data-icon="octicon-repo-forked" aria-label="Fork fgmacedo/python-statemachine on GitHub">Fork</a>

- If you found this project helpful, please consider giving it a star on GitHub.

- **Contribute code**: If you would like to contribute code to this project, please submit a pull
request. For more information on how to contribute, please see our [contributing.md]contributing.md) file.

- **Report bugs**: If you find any bugs in this project, please report them by opening an issue
  on our GitHub issue tracker.

- **Suggest features**: If you have a great idea for a new feature, please let us know by opening
  an issue on our GitHub issue tracker.

- **Documentation**: Help improve this project's documentation by submitting pull requests.

- **Promote the project**: Help spread the word about this project by sharing it on social media,
  writing a blog post, or giving a talk about it. Tag me on Twitter
  [@fgmacedo](https://twitter.com/fgmacedo) so I can share it too!
