
(observers)=
# Listeners

Listeners are a way to generically add behavior to a state machine without
changing its internal implementation.

One possible use case is to add a listener that prints a log message when the SM runs a
transition or enters a new state.

Giving the {ref}`sphx_glr_auto_examples_traffic_light_machine.py` as example:


```py
>>> from tests.examples.traffic_light_machine import TrafficLightMachine

>>> class LogListener(object):
...     def __init__(self, name):
...         self.name = name
...
...     def after_transition(self, event, source, target):
...         print(f"{self.name} after: {source.id}--({event})-->{target.id}")
...
...     def on_enter_state(self, target, event):
...         print(f"{self.name} enter: {target.id} from {event}")


>>> sm = TrafficLightMachine(listeners=[LogListener("Paulista Avenue")])
Paulista Avenue enter: green from __initial__

>>> sm.cycle()
Running cycle from green to yellow
Paulista Avenue enter: yellow from cycle
Paulista Avenue after: green--(cycle)-->yellow

```

## Adding listeners to an instance

Attach listeners to an already running state machine instance using `add_listener`.

Exploring our example, imagine that you can implement the LED panel as a listener, that
reacts to state changes and turn on/off automatically.


``` py
>>> class LedPanel:
...
...     def __init__(self, color: str):
...         self.color = color
...
...     def on_enter_state(self, target: State):
...         if target.id == self.color:
...             print(f"{self.color} turning on")
...
...     def on_exit_state(self, source: State):
...         if source.id == self.color:
...             print(f"{self.color} turning off")

```

Adding a listener for each traffic light indicator

```
>>> sm.add_listener(LedPanel("green"), LedPanel("yellow"), LedPanel("red"))  # doctest: +ELLIPSIS
TrafficLightMachine...

```

Now each "LED panel" reacts to changes in state from the state machine:

```py
>>> sm.cycle()
Running cycle from yellow to red
yellow turning off
Paulista Avenue enter: red from cycle
red turning on
Paulista Avenue after: yellow--(cycle)-->red

>>> sm.cycle()
Running cycle from red to green
red turning off
Paulista Avenue enter: green from cycle
green turning on
Paulista Avenue after: red--(cycle)-->green

```


```{hint}
The `StateMachine` itself is registered as a listener, so by using `listeners` an
external object can have the same level of functionalities provided to the built-in class.
```

```{tip}
{ref}`domain models` are also registered as a listener.
```


```{seealso}
See {ref}`actions`, {ref}`validators and guards` for a list of possible callbacks.

And also {ref}`dynamic-dispatch` to know more about how the lib calls methods to match
their signature.
```
