
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


## Class-level listener declarations

```{versionadded} 3.0.0
```

You can declare listeners at the class level so they are automatically attached to every
instance of the state machine. This is useful for cross-cutting concerns like logging,
persistence, or telemetry that should always be present.

The `listeners` class attribute accepts two forms:

- **Callable** (class, `functools.partial`, lambda): acts as a factory — called once per
  SM instance to produce a fresh listener. Use this for listeners that accumulate state.
- **Instance** (pre-built object): shared across all SM instances. Use this for stateless
  listeners like a global logger.

```py
>>> from statemachine import State, StateChart

>>> class AuditListener:
...     def __init__(self):
...         self.log = []
...
...     def after_transition(self, event, source, target):
...         self.log.append(f"{event}: {source.id} -> {target.id}")

>>> class OrderMachine(StateChart):
...     listeners = [AuditListener]
...
...     draft = State(initial=True)
...     confirmed = State(final=True)
...     confirm = draft.to(confirmed)

>>> sm = OrderMachine()
>>> sm.send("confirm")
>>> [type(l).__name__ for l in sm.active_listeners]
['AuditListener']

>>> sm.active_listeners[0].log
['confirm: draft -> confirmed']

```

### Listeners with configuration

Use `functools.partial` to pass configuration to listener factories:

```py
>>> from functools import partial

>>> class HistoryListener:
...     def __init__(self, max_size=50):
...         self.max_size = max_size
...         self.entries = []
...
...     def after_transition(self, event, source, target):
...         self.entries.append(f"{source.id} -> {target.id}")
...         if len(self.entries) > self.max_size:
...             self.entries.pop(0)

>>> class TrackedMachine(StateChart):
...     listeners = [partial(HistoryListener, max_size=10)]
...
...     s1 = State(initial=True)
...     s2 = State(final=True)
...     go = s1.to(s2)

>>> sm = TrackedMachine()
>>> sm.send("go")
>>> sm.active_listeners[0].entries
['s1 -> s2']

```

### Runtime listeners merge with class-level

Runtime listeners passed via the `listeners=` constructor parameter are appended after
class-level listeners:

```py
>>> runtime_listener = AuditListener()
>>> sm = OrderMachine(listeners=[runtime_listener])
>>> sm.send("confirm")
>>> [type(l).__name__ for l in sm.active_listeners]
['AuditListener', 'AuditListener']

>>> runtime_listener.log
['confirm: draft -> confirmed']

```

### Inheritance

Child class listeners are appended after parent listeners. The full MRO chain is respected:

```py
>>> class LogListener:
...     pass

>>> class BaseMachine(StateChart):
...     listeners = [LogListener]
...
...     s1 = State(initial=True)
...     s2 = State(final=True)
...     go = s1.to(s2)

>>> class ChildMachine(BaseMachine):
...     listeners = [AuditListener]

>>> sm = ChildMachine()
>>> [type(l).__name__ for l in sm.active_listeners]
['LogListener', 'AuditListener']

```

To **replace** parent listeners instead of extending, set `listeners_inherit = False`:

```py
>>> class ReplacedMachine(BaseMachine):
...     listeners_inherit = False
...     listeners = [AuditListener]

>>> sm = ReplacedMachine()
>>> [type(l).__name__ for l in sm.active_listeners]
['AuditListener']

```

### Listener `setup()` protocol

Listeners that need runtime dependencies (e.g., a database session, Redis client) can
define a `setup()` method. It is called during SM `__init__` with the SM instance and
any extra `**kwargs` passed to the constructor. The {ref}`dynamic-dispatch` mechanism
ensures each listener receives only the kwargs it declares:

```py
>>> class DBListener:
...     def __init__(self):
...         self.session = None
...
...     def setup(self, sm, session=None, **kwargs):
...         self.session = session

>>> class PersistentMachine(StateChart):
...     listeners = [DBListener]
...
...     s1 = State(initial=True)
...     s2 = State(final=True)
...     go = s1.to(s2)

>>> sm = PersistentMachine(session="my_db_session")
>>> sm.active_listeners[0].session
'my_db_session'

```

Multiple listeners with different dependencies compose naturally — each `setup()` picks
only the kwargs it needs:

```py
>>> class CacheListener:
...     def __init__(self):
...         self.redis = None
...
...     def setup(self, sm, redis=None, **kwargs):
...         self.redis = redis

>>> class FullMachine(StateChart):
...     listeners = [DBListener, CacheListener]
...
...     s1 = State(initial=True)
...     s2 = State(final=True)
...     go = s1.to(s2)

>>> sm = FullMachine(session="db_conn", redis="redis_conn")
>>> sm.active_listeners[0].session
'db_conn'
>>> sm.active_listeners[1].redis
'redis_conn'

```

```{note}
The `setup()` method is only called on **factory-created** instances (callable entries).
Shared instances (pre-built objects) do not receive `setup()` calls — they are assumed
to be already configured by whoever created them.
```

```{hint}
The `StateChart` itself is registered as a listener, so by using `listeners` an
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
