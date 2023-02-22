
# Observers

Observers are a way to generically add behavior to a StateMachine without
changing its internal implementation.

One possible use case is to add an observer that prints a log message when the SM runs a
transition or enters a new state.

Giving the {ref}`sphx_glr_auto_examples_traffic_light_machine.py` as example:


```py
>>> from tests.examples.traffic_light_machine import TrafficLightMachine

>>> class LogObserver(object):
...     def __init__(self, name):
...         self.name = name
...
...     def after_transition(self, event, source, target):
...         print(f"{self.name} after: {source.id}--({event})-->{target.id}")
...
...     def on_enter_state(self, target, event):
...         print(f"{self.name} enter: {target.id} from {event}")


>>> sm = TrafficLightMachine()

>>> sm.add_observer(LogObserver("Paulista Avenue"))  # doctest: +ELLIPSIS
TrafficLightMachine...

>>> sm.cycle()
Paulista Avenue enter: yellow from cycle
Paulista Avenue after: green--(cycle)-->yellow
'Running cycle from green to yellow'

```

```{hint}
The `StateMachine` itself is registered as an observer, so by using `.add_observer()` an
external object can have the same level of functionalities provided to the built-in class.
```

```{tip}
{ref}`domain models` are also registered as an observer.
```


```{seealso}
See {ref}`actions`, {ref}`validators and guards` for a list of possible callbacks.

And also {ref}`dynamic-dispatch` to know more about how the lib calls methods to match
their signature.
```
