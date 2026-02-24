(events)=
(event)=
# Events

```{seealso}
New to statecharts? See [](concepts.md) for an overview of how states,
transitions, events, and actions fit together.
```

An **event** is a named signal that drives the state machine forward. When you
assign a transition to a class-level name, that name becomes an event — the
library creates an `Event` object automatically. Events are the external
interface of your machine: callers send event names, and the machine decides
which transitions to take.


(declaring-events)=

## Declaring events

The simplest way to declare an event is by assigning a transition to a name:

```py
>>> from statemachine import Event, State, StateChart

>>> class SimpleSM(StateChart):
...     initial = State(initial=True)
...     final = State(final=True)
...
...     start = initial.to(final)

>>> isinstance(SimpleSM.start, Event)
True

```

The name `start` is automatically converted to an `Event` with
`id="start"`. Multiple transitions can share the same event using
the `|` operator:

```py
>>> class TrafficLight(StateChart):
...     green = State(initial=True)
...     yellow = State()
...     red = State()
...
...     cycle = green.to(yellow) | yellow.to(red) | red.to(green)

>>> sm = TrafficLight()
>>> sm.send("cycle")
>>> sm.yellow.is_active
True

```

For better IDE support (autocompletion, type checking) or to set a
human-readable display name, use the `Event` class explicitly:

```py
>>> class SimpleSM(StateChart):
...     initial = State(initial=True)
...     final = State(final=True)
...
...     start = Event(initial.to(final), name="Start the machine")

>>> SimpleSM.start.name
'Start the machine'

>>> SimpleSM.start.id
'start'

```


(event-identity)=

## Event identity: `id` vs `name`

Every event has two string properties:

- **`id`** — the programmatic identifier, derived from the class attribute name.
  Use this in `send()`, guards, and comparisons.
- **`name`** — a human-readable label for display purposes. Defaults to the `id`
  when not explicitly set.

```py
>>> TrafficLight.cycle.id
'cycle'

>>> TrafficLight.cycle.name
'cycle'

```

```{tip}
Always use `event.id` for programmatic checks. The `name` property is intended
for UI display and may change format in future versions.
```


(triggering-events)=
(triggering events)=

## Triggering events

Once declared, events are triggered on a {ref}`StateChart <statechart>` instance
in two ways:

- **As a method call:** `sm.cycle()` — when the event name is known at
  development time.
- **Via `send()`:** `sm.send("cycle")` — when the event name is dynamic (e.g.,
  from user input, a message queue, or a data file).

Both styles produce the same result. The machine evaluates
{ref}`guard conditions <validators and guards>`, executes {ref}`actions`, and
updates the {ref}`configuration <querying-configuration>`.

```{seealso}
See {ref}`sending-events` for the full runtime API — `send()`, `raise_()`,
delayed events, and cancellation.
```


(event-parameter)=

## The `event` parameter on transitions

Each transition accepts an optional `event` parameter that binds it to a
specific event, overriding the default (which is the class-level attribute
name). This lets individual transitions within a group respond to their own
event identifiers:

```py
>>> from statemachine import Event, State, StateChart

>>> class TrafficLightMachine(StateChart):
...     green = State(initial=True)
...     yellow = State()
...     red = State()
...
...     slowdown = Event(name="Slowing down")
...
...     cycle = Event(
...         green.to(yellow, event=slowdown)
...         | yellow.to(red, event="stop")
...         | red.to(green, event="go"),
...         name="Loop",
...     )

>>> sm = TrafficLightMachine()

>>> sm.send("cycle")  # umbrella event — dispatches green→yellow
>>> sm.yellow.is_active
True

>>> sm.send("stop")   # individual event — dispatches yellow→red
>>> sm.red.is_active
True

>>> sm.send("go")     # individual event — dispatches red→green
>>> sm.green.is_active
True

```

The `event` parameter accepts a string, an `Event` instance, a reference
to a previously declared `Event` (like `slowdown` above), or a **list** of
any of these. A space-separated string is also accepted and split into
individual events automatically:

```py
>>> class MultiEvent(StateChart):
...     a = State(initial=True)
...     b = State(final=True)
...
...     # Both forms are equivalent — the transition responds to "move", "go" and "start"
...     move = a.to(b, event=["go", "start"])

>>> sm = MultiEvent()
>>> sm.send("move")
>>> sm.b.is_active
True

>>> sm = MultiEvent()
>>> sm.send("go")
>>> sm.b.is_active
True

>>> sm = MultiEvent()
>>> sm.send("start")
>>> sm.b.is_active
True

```

```{tip}
This is an advanced feature. Most state machines only need the simple
`name = source.to(target)` form. Use the `event` parameter when you need
fine-grained control over event routing within a composite transition group.
```


(done-state-events)=

## Automatic events

The engine generates certain events automatically in response to structural
changes. You don't send these yourself — you define transitions that react
to them.


### `done.state` events

```{versionadded} 3.0.0
```

When a {ref}`compound state's <compound-states>` final child is entered, the
engine queues a `done.state.{parent_id}` internal event. Define a transition
for this event to react when a compound's work is complete:

```py
>>> from statemachine import State, StateChart

>>> class QuestWithDone(StateChart):
...     class quest(State.Compound):
...         traveling = State(initial=True)
...         arrived = State(final=True)
...         finish = traveling.to(arrived)
...     celebration = State(final=True)
...     done_state_quest = quest.to(celebration)

>>> sm = QuestWithDone()
>>> sm.send("finish")
>>> set(sm.configuration_values) == {"celebration"}
True

```

For {ref}`parallel states <parallel-states>`, the `done.state` event fires
only when **all** regions have reached a final state:

```py
>>> from statemachine import State, StateChart

>>> class WarWithDone(StateChart):
...     class war(State.Parallel):
...         class quest(State.Compound):
...             start_q = State(initial=True)
...             end_q = State(final=True)
...             finish_q = start_q.to(end_q)
...         class battle(State.Compound):
...             start_b = State(initial=True)
...             end_b = State(final=True)
...             finish_b = start_b.to(end_b)
...     peace = State(final=True)
...     done_state_war = war.to(peace)

>>> sm = WarWithDone()
>>> sm.send("finish_q")
>>> "war" in sm.configuration_values
True

>>> sm.send("finish_b")
>>> set(sm.configuration_values) == {"peace"}
True

```

(donedata)=

#### DoneData

Final states can carry data to their `done.state` handlers via the `donedata`
parameter. The value should be a callable (or method name string) that returns
a `dict`, which is forwarded as keyword arguments to the transition handler:

```py
>>> from statemachine import Event, State, StateChart

>>> class QuestCompletion(StateChart):
...     class quest(State.Compound):
...         traveling = State(initial=True)
...         completed = State(final=True, donedata="get_result")
...         finish = traveling.to(completed)
...         def get_result(self):
...             return {"hero": "frodo", "outcome": "victory"}
...     epilogue = State(final=True)
...     done_state_quest = Event(quest.to(epilogue, on="capture_result"))
...     def capture_result(self, hero=None, outcome=None, **kwargs):
...         self.result = f"{hero}: {outcome}"

>>> sm = QuestCompletion()
>>> sm.send("finish")
>>> sm.result
'frodo: victory'

```

```{note}
`donedata` can only be specified on `final=True` states. Attempting to use it
on a non-final state raises `InvalidDefinition`.
```


### `error.execution` events

When a callback raises during a macrostep and
{ref}`catch_errors_as_events <behaviour>` is enabled, the engine dispatches an
`error.execution` internal event. Define a transition for this event to
recover from errors within the statechart:

```py
>>> from statemachine import State, StateChart

>>> class ResilientChart(StateChart):
...     working = State(initial=True)
...     failed = State(final=True)
...
...     go = working.to.itself(on="do_work")
...     error_execution = working.to(failed)
...
...     def do_work(self):
...         raise RuntimeError("something went wrong")

>>> sm = ResilientChart()
>>> sm.send("go")
>>> "failed" in sm.configuration_values
True

```

```{seealso}
See {ref}`error-execution` for the full error handling reference: recovery
patterns, `after` as a finalize hook, and nested error scenarios.
```


(naming-conventions)=

## Dot-notation naming conventions

SCXML uses dot-separated event names (`done.state.quest`, `error.execution`),
but Python identifiers cannot contain dots. The library provides prefix-based
naming conventions that automatically register both forms:

(done-state-convention)=

### `done_state_` prefix

Any event attribute starting with `done_state_` matches both the underscore
form and the dot-notation form. Only the prefix is replaced — the suffix is
kept as-is, preserving multi-word state names:

| Attribute name                | Matches event names |
|-------------------------------|---------------------|
| `done_state_quest`            | `"done_state_quest"` and `"done.state.quest"` |
| `done_state_lonely_mountain`  | `"done_state_lonely_mountain"` and `"done.state.lonely_mountain"` |


### `error_` prefix

Any event attribute starting with `error_` matches both the underscore form
and the dot-notation form. Unlike `done_state_`, **all** underscores after
the prefix are replaced with dots:

| Attribute name       | Matches event names |
|----------------------|---------------------|
| `error_execution`    | `"error_execution"` and `"error.execution"` |

```{note}
If you provide an explicit `id=` parameter on the `Event`, it takes precedence
and the naming convention is not applied.
```
