(observers)=
(listeners)=

# Listeners

A **listener** is an external object that observes a state machine's lifecycle
without modifying its class definition. Listeners receive the same
{ref}`generic callbacks <actions>` as the state machine itself —
`on_enter_state()`, `after_transition()`, `on_exit_state()`, and so on —
making them ideal for cross-cutting concerns like logging, persistence,
telemetry, or UI updates.

Under the hood, the `StateChart` class itself is registered as a listener —
this is how naming-convention callbacks like `on_enter_idle()` are
discovered. {ref}`Domain models <models>` are also registered as listeners.
This means that an external listener has the **same level of access** to
callbacks as methods defined directly on the state machine class.

```{tip}
Why use a listener instead of defining callbacks directly on the class?
Listeners keep concerns **separate and reusable** — the same logging
listener can observe any state machine, and you can attach multiple
independent listeners without them interfering with each other.
```


## Defining a listener

A listener is any object with methods that match the
{ref}`callback naming conventions <actions>`. The library inspects the
method signatures and calls them with {ref}`dependency injection <dependency-injection>`,
so each listener receives only the parameters it declares:

```py
>>> from statemachine import State, StateChart

>>> class LogListener:
...     def __init__(self, name):
...         self.name = name
...
...     def after_transition(self, event, source, target):
...         print(f"{self.name} after: {source.id}--({event})-->{target.id}")
...
...     def on_enter_state(self, target, event):
...         print(f"{self.name} enter: {target.id} from {event}")

```

No base class or interface is required — any object with matching method
names works.


## Class-level declarations

The most common way to attach listeners is at the class level, using the
`listeners` class attribute. This ensures listeners are automatically
created for every instance:

```py
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
>>> sm.active_listeners[0].log
['confirm: draft -> confirmed']

```

The `listeners` attribute accepts two forms:

- **Callable** (class, `functools.partial`, lambda): acts as a **factory** —
  called once per instance to produce a fresh listener. Use this for
  listeners that accumulate state.
- **Instance** (pre-built object): **shared** across all instances. Use
  this for stateless listeners like a global logger.


### Configuration with `functools.partial`

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


### Inheritance

Child class listeners are appended after parent listeners. The full MRO
chain is respected:

```py
>>> class SimpleLogListener:
...     def after_transition(self, event, source, target):
...         pass

>>> class BaseMachine(StateChart):
...     listeners = [SimpleLogListener]
...
...     s1 = State(initial=True)
...     s2 = State(final=True)
...     go = s1.to(s2)

>>> class ChildMachine(BaseMachine):
...     listeners = [AuditListener]

>>> sm = ChildMachine()
>>> [type(l).__name__ for l in sm.active_listeners]
['SimpleLogListener', 'AuditListener']

```

To **replace** parent listeners instead of extending, set
`listeners_inherit = False`:

```py
>>> class ReplacedMachine(BaseMachine):
...     listeners_inherit = False
...     listeners = [AuditListener]

>>> sm = ReplacedMachine()
>>> [type(l).__name__ for l in sm.active_listeners]
['AuditListener']

```


## Attaching at construction

Pass listeners to the constructor for instance-specific observers.
Runtime listeners are appended **after** class-level listeners:

```py
>>> runtime_listener = AuditListener()
>>> sm = OrderMachine(listeners=[runtime_listener])
>>> sm.send("confirm")
>>> [type(l).__name__ for l in sm.active_listeners]
['AuditListener', 'AuditListener']

>>> runtime_listener.log
['confirm: draft -> confirmed']

```


## Attaching at runtime

Use `add_listener()` to attach listeners to an already running instance.
This is useful when the listener depends on runtime context or when you
want to start observing after initialization:

```py
>>> class LedPanel:
...     def __init__(self, color):
...         self.color = color
...         self.is_on = False
...
...     def on_enter_state(self, target, **kwargs):
...         if target.id == self.color:
...             self.is_on = True
...
...     def on_exit_state(self, source, **kwargs):
...         if source.id == self.color:
...             self.is_on = False

>>> class TrafficLight(StateChart):
...     green = State(initial=True)
...     yellow = State()
...     red = State()
...
...     cycle = green.to(yellow) | yellow.to(red) | red.to(green)

>>> sm = TrafficLight()
>>> green_led = LedPanel("green")
>>> yellow_led = LedPanel("yellow")
>>> sm.add_listener(green_led, yellow_led)  # doctest: +ELLIPSIS
TrafficLight...

>>> green_led.is_on, yellow_led.is_on
(False, False)

>>> sm.send("cycle")
>>> green_led.is_on, yellow_led.is_on
(False, True)

```


## The `setup()` protocol

Listeners that need runtime dependencies (e.g., a database session, a
Redis client) can define a `setup()` method. It is called during the
state machine's `__init__` with the instance and any extra `**kwargs`
passed to the constructor. {ref}`Dependency injection <dependency-injection>`
ensures each listener receives only the kwargs it declares:

```py
>>> class DBListener:
...     def __init__(self):
...         self.session = None
...
...     def setup(self, sm, session=None, **kwargs):
...         self.session = session

>>> class CacheListener:
...     def __init__(self):
...         self.redis = None
...
...     def setup(self, sm, redis=None, **kwargs):
...         self.redis = redis

>>> class PersistentMachine(StateChart):
...     listeners = [DBListener, CacheListener]
...
...     s1 = State(initial=True)
...     s2 = State(final=True)
...     go = s1.to(s2)

>>> sm = PersistentMachine(session="db_conn", redis="redis_conn")
>>> sm.active_listeners[0].session
'db_conn'
>>> sm.active_listeners[1].redis
'redis_conn'

```

Multiple listeners with different dependencies compose naturally — each
`setup()` picks only the kwargs it needs.

```{note}
The `setup()` method is only called on **factory-created** instances
(callable entries in the `listeners` list). Shared instances (pre-built
objects) do not receive `setup()` calls — they are assumed to be already
configured.
```


```{seealso}
See {ref}`actions` for the full list of callback groups and
{ref}`dependency injection <dependency-injection>` for how method
signatures are matched.
```
