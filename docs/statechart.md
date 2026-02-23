(statechart-instance)=
(statechart)=
(statemachine)=

# StateChart

```{seealso}
New to statecharts? See [](concepts.md) for an overview of how states,
transitions, events, and actions fit together.
```

Once you define a `StateChart` class with states, transitions, and events, you
work with **instances** of that class. Each instance is a live, running machine
with its own configuration, event queues, and listeners. This page documents what
you can do with that instance at runtime.


## Creating an instance

```py
>>> from statemachine import State, StateChart

>>> class TrafficLight(StateChart):
...     green = State(initial=True)
...     yellow = State()
...     red = State()
...
...     cycle = green.to(yellow) | yellow.to(red) | red.to(green)

>>> sm = TrafficLight()

```

The constructor activates the initial state and runs any `on_enter` callbacks.
You can pass a `model` object to store state externally (see {ref}`models`) and
`listeners` to observe the machine (see {ref}`listeners`).


(sending-events)=

## Sending events

The primary way to drive a state machine is by sending events.

**`send(event, **kwargs)`** places the event on the **external queue**. External
events are processed after the current macrostep completes:

```py
>>> sm.send("cycle")
>>> sm.yellow.is_active
True

```

Events can also be called as methods — `sm.cycle()` is equivalent to
`sm.send("cycle")`:

```py
>>> sm.cycle()
>>> sm.red.is_active
True

```

**`raise_(event, **kwargs)`** places the event on the **internal queue**. Internal
events are processed within the current macrostep, before any pending external
events. This is useful inside callbacks when you need to trigger follow-up
transitions immediately:

```py
>>> from statemachine import State, StateChart

>>> class WithInternalEvent(StateChart):
...     a = State(initial=True)
...     b = State()
...     c = State(final=True)
...
...     go = a.to(b)
...     finish = b.to(c)
...
...     def on_enter_b(self):
...         self.raise_("finish")

>>> sm = WithInternalEvent()
>>> sm.send("go")
>>> sm.c.is_active
True

```

Both methods accept arbitrary keyword arguments that are forwarded to all
callbacks via {ref}`dependency injection <dependency-injection>`.

```{seealso}
See {ref}`processing model` for the full macrostep/microstep lifecycle and how
internal and external queues interact.
```

(delayed-events)=

### Delayed events

Events can be scheduled to fire after a delay (in milliseconds):

```python
sm.send("timeout", delay=5000)
```

Delayed events can be cancelled before firing by providing a `send_id`:

```python
sm.send("timeout", delay=5000, send_id="my_timeout")
sm.cancel_event("my_timeout")
```

```{note}
The delay is **blocking** in the sync engine — the processing loop sleeps until the
delay elapses, holding the calling thread. In the async engine, delays are scheduled
with `asyncio` and do not block the event loop.
```


(querying-events)=

## Querying events

Not every event is relevant in every state. The instance provides two levels
of event introspection:

**`allowed_events`** — events that have at least one transition **from the
current configuration**, regardless of whether guards pass:

```py
>>> from statemachine import State, StateChart

>>> class Turnstile(StateChart):
...     locked = State(initial=True)
...     unlocked = State()
...
...     coin = locked.to(unlocked)
...     push = unlocked.to(locked)

>>> sm = Turnstile()
>>> [e.id for e in sm.allowed_events]
['coin']

```

**`enabled_events(**kwargs)`** — a subset of `allowed_events` where at least one
transition's guards are **satisfied** given the provided arguments. Use this when
guards depend on runtime data:

```py
>>> from statemachine import State, StateChart

>>> class Gate(StateChart):
...     closed = State(initial=True)
...     open = State()
...
...     enter = closed.to(open, cond="has_badge")
...     close = open.to(closed)
...
...     def has_badge(self, badge: bool = False):
...         return badge

>>> sm = Gate()
>>> [e.id for e in sm.allowed_events]
['enter']

>>> [e.id for e in sm.enabled_events()]
[]

>>> [e.id for e in sm.enabled_events(badge=True)]
['enter']

```

`allowed_events` is cheap — it only checks the state topology. `enabled_events`
evaluates guards, so pass the same keyword arguments you would pass to `send()`.


(querying-configuration)=

## Querying the configuration

The **configuration** is the set of currently active states. In a flat machine
this is a single state; with compound and parallel states, multiple states are
active simultaneously.

**`configuration`** returns the active states as an `OrderedSet[State]`:

```py
>>> from statemachine import State, StateChart

>>> class Journey(StateChart):
...     class shire(State.Compound):
...         bag_end = State(initial=True)
...         green_dragon = State()
...         visit_pub = bag_end.to(green_dragon)
...     road = State(final=True)
...     depart = shire.to(road)

>>> sm = Journey()
>>> {s.id for s in sm.configuration} == {"shire", "bag_end"}
True

```

**`configuration_values`** returns the values (or IDs when no custom `value` is
set) instead of `State` objects — useful for serialization or quick checks:

```py
>>> set(sm.configuration_values) == {"shire", "bag_end"}
True

```


(checking-termination)=

## Checking termination

**`is_terminated`** returns `True` when the machine has completed its work. In a
flat machine this means a final state is active. With compound and parallel
states, the condition is structural — all parallel regions must have completed,
nested compounds must have reached their final children, and so on:

```py
>>> sm.send("visit_pub")
>>> sm.is_terminated
False

>>> sm.send("depart")
>>> sm.is_terminated
True

```

Use `is_terminated` instead of checking individual states — it handles
arbitrarily nested structures for you.

**`final_states`** lists all top-level states marked as `final`:

```py
>>> sm.final_states
[State('Road', id='road', value='road', initial=False, final=True, parallel=False)]

```


(runtime-listeners)=

## Managing listeners at runtime

Class-level listeners are declared on the class (see {ref}`listeners`). You can
also add listeners to a running instance:

```py
>>> class Logger:
...     def after_transition(self, source: State, target: State, event: str):
...         print(f"[log] {source.id} →({event})→ {target.id}")

>>> sm = Turnstile()
>>> _ = sm.add_listener(Logger())
>>> sm.send("coin")
[log] locked →(coin)→ unlocked

```

`add_listener()` returns the instance for chaining. Use `active_listeners` to
inspect all currently attached listeners.


## Class-level attributes

These are set by the metaclass at class definition time and are available on both
the class and its instances:

| Attribute | Type | Description |
|---|---|---|
| `name` | `str` | The class name (e.g., `"TrafficLight"`) |
| `states` | `States` | Collection of all top-level states |
| `final_states` | `list[State]` | Top-level states marked as `final` |
| `events` | `list[Event]` | All events declared on the class |
| `initial_state` | `State` | The top-level initial state |
| `states_map` | `dict` | Mapping from state values to `State` objects (all nesting levels) |
