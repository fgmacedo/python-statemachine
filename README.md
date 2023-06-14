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
...     cycle = (
...         green.to(yellow)
...         | yellow.to(red)
...         | red.to(green)
...     )
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
>>> sm = TrafficLightMachine()

```

This state machine can be represented graphically as follows:

```py
>>> img_path = "docs/images/readme_trafficlightmachine.png"
>>> sm._graph().write_png(img_path)

```

![](https://raw.githubusercontent.com/fgmacedo/python-statemachine/develop/docs/images/readme_trafficlightmachine.png)


Where on the `TrafficLightMachine`, we've defined `green`, `yellow`, and `red` as states, and
one event called `cycle`, which is bound to the transitions from `green` to `yellow`, `yellow` to `red`,
and `red` to `green`. We also have defined three callbacks by name convention, `before_cycle`, `on_enter_red`, and `on_exit_red`.


Then start sending events to your new state machine:

```py
>>> sm.send("cycle")
'Running cycle from green to yellow'

```

That's it. This is all an external object needs to know about your state machine: How to send events.
Ideally, all states, transitions, and actions should be kept internally and not checked externally to avoid unnecessary coupling.

But if your use case needs, you can inspect state machine properties, like the current state:

```py
>>> sm.current_state.id
'yellow'

```

Or get a complete state representation for debugging purposes:

```py
>>> sm.current_state
State('Yellow', id='yellow', value='yellow', initial=False, final=False)

```

The `State` instance can also be checked by equality:

```py
>>> sm.current_state == TrafficLightMachine.yellow
True

>>> sm.current_state == sm.yellow
True

```

Or you can check if a state is active at any time:

```py
>>> sm.green.is_active
False

>>> sm.yellow.is_active
True

>>> sm.red.is_active
False

```

Easily iterate over all states:

```py
>>> [s.id for s in sm.states]
['green', 'red', 'yellow']

```

Or over events:

```py
>>> [t.name for t in sm.events]
['cycle']

```

Call an event by its name:

```py
>>> sm.cycle()
Don't move.
'Running cycle from yellow to red'

```
Or send an event with the event name:

```py
>>> sm.send('cycle')
Go ahead!
'Running cycle from red to green'

>>> sm.green.is_active
True

```

You can pass arbitrary positional or keyword arguments to the event, and
they will be propagated to all actions and callbacks using something similar to dependency injection. In other words, the library will only inject the parameters declared on the
callback method.

Note how `before_cycle` was declared:

```py
def before_cycle(self, event: str, source: State, target: State, message: str = ""):
    message = ". " + message if message else ""
    return f"Running {event} from {source.id} to {target.id}{message}"
```

The params `event`, `source`, `target` (and others) are available built-in to be used on any action.
The param `message` is user-defined, in our example we made it default empty so we can call `cycle` with
or without a `message` parameter.

If we pass a `message` parameter, it will be used on the `before_cycle` action:

```py
>>> sm.send("cycle", message="Please, now slowdown.")
'Running cycle from green to yellow. Please, now slowdown.'

```


By default, events with transitions that cannot run from the current state or unknown events
raise a `TransitionNotAllowed` exception:

```py
>>> sm.send("go")
Traceback (most recent call last):
statemachine.exceptions.TransitionNotAllowed: Can't go when in Yellow.

```

Keeping the same state as expected:

```py
>>> sm.yellow.is_active
True

```

A human-readable name is automatically derived from the `State.id`, which is used on the messages
and in diagrams:

```py
>>> sm.current_state.name
'Yellow'

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
request. For more information on how to contribute, please see our [contributing.md](contributing.md) file.

- **Report bugs**: If you find any bugs in this project, please report them by opening an issue
  on our GitHub issue tracker.

- **Suggest features**: If you have a great idea for a new feature, please let us know by opening
  an issue on our GitHub issue tracker.

- **Documentation**: Help improve this project's documentation by submitting pull requests.

- **Promote the project**: Help spread the word about this project by sharing it on social media,
  writing a blog post, or giving a talk about it. Tag me on Twitter
  [@fgmacedo](https://twitter.com/fgmacedo) so I can share it too!
