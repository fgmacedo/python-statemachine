```{testsetup}

>>> from statemachine import StateChart, State

```

(events)=
(event)=
# Events

```{seealso}
New to statecharts? See [](concepts.md) for an overview of how states,
transitions, events, and actions fit together.
```

An event is an external signal that something has happened. Events trigger
{ref}`transitions <transitions>`, causing the state machine to react and
move between states.


(declaring-events)=

## Declaring events

The simplest way to declare an {ref}`event` is by assigning a transition to a
name at the class level. The name is automatically converted to an {ref}`Event`:

```py
>>> from statemachine import Event

>>> class SimpleSM(StateChart):
...     initial = State(initial=True)
...     final = State(final=True)
...
...     start = initial.to(final)  # start is a name that will be converted to an `Event`

>>> isinstance(SimpleSM.start, Event)
True
>>> sm = SimpleSM()
>>> sm.start()  # call `start` event

```

```{versionadded} 2.4.0
You can also explictly declare an {ref}`Event` instance, this helps IDEs to know that the event is callable, and also with translation strings.
```

To declare an explicit event you must also import the {ref}`Event`:

```py
>>> from statemachine import Event

>>> class SimpleSM(StateChart):
...     initial = State(initial=True)
...     final = State(final=True)
...
...     start = Event(
...         initial.to(final),
...         name="Start the state machine"  # optional name, if not provided it will be derived from id
...     )

>>> SimpleSM.start.name
'Start the state machine'

>>> sm = SimpleSM()
>>> sm.start()  # call `start` event

```

### The `event` parameter on transitions

Each transition accepts an optional `event` parameter that binds it to a
specific event, overriding the default (which is the class-level attribute
name). This lets you group transitions under one umbrella event while giving
individual transitions their own event identifiers. The `event` parameter
accepts a string, an `Event` instance, or a previously declared `Event`:

```py
>>> from statemachine import State, StateChart, Event

>>> class TrafficLightMachine(StateChart):
...     "A traffic light machine"
...
...     green = State(initial=True)
...     yellow = State()
...     red = State()
...
...     slowdown = Event(name="Slowing down")
...
...     cycle = Event(
...         green.to(yellow, event=slowdown)
...         | yellow.to(red, event=Event("stop", name="Please stop!"))
...         | red.to(green, event="go"),
...         name="Loop",
...     )
...
...     def on_transition(self, event_data, event: Event):
...         # The `event` parameter can be declared as `str` or `Event`, since `Event` is a subclass of `str`
...         # Note also that in this example, we're using `on_transition` instead of `on_cycle`, as this
...         # binds the action to run for every transition instead of a specific event ID.
...         assert event_data.event == event
...         return (
...             f"Running {event.name} from {event_data.transition.source.id} to "
...             f"{event_data.transition.target.id}"
...         )

>>> # Event IDs
>>> TrafficLightMachine.cycle.id
'cycle'
>>> TrafficLightMachine.slowdown.id
'slowdown'
>>> TrafficLightMachine.stop.id
'stop'
>>> TrafficLightMachine.go.id
'go'

>>> # Event names
>>> TrafficLightMachine.cycle.name
'Loop'
>>> TrafficLightMachine.slowdown.name
'Slowing down'
>>> TrafficLightMachine.stop.name
'Please stop!'
>>> TrafficLightMachine.go.name
'go'

>>> sm = TrafficLightMachine()

>>> sm.cycle()  # Your IDE is happy because it now knows that `cycle` is callable!
'Running Loop from green to yellow'

>>> sm.send("cycle")  # You can also use `send` in order to process dynamic event sources
'Running Loop from yellow to red'

>>> sm.send("cycle")
'Running Loop from red to green'

>>> sm.send("slowdown")
'Running Slowing down from green to yellow'

>>> sm.send("stop")
'Running Please stop! from yellow to red'

>>> sm.send("go")
'Running go from red to green'

```

```{tip}
Avoid mixing these options within the same project; instead, choose the one that best serves your use case. Declaring events as strings has been the standard approach since the library's inception and can be considered syntactic sugar, as the state machine metaclass will convert all events to {ref}`Event` instances under the hood.

```

```{note}
In order to allow the seamless upgrade from using strings to `Event` instances, the {ref}`Event` inherits from `str`.

Note that this is just an implementation detail and can change in the future.

    >>> isinstance(TrafficLightMachine.cycle, str)
    True

```


```{warning}

An {ref}`Event` declared as string will have its `name` set equal to its `id`. This is for backward compatibility when migrating from previous versions.

In the next major release, `Event.name` will default to a capitalized version of `id` (i.e., `Event.id.replace("_", " ").capitalize()`).

Starting from version 2.4.0, use `Event.id` to check for event identifiers instead of `Event.name`.

```


(triggering-events)=
(triggering events)=

## Triggering events

There are two ways to trigger an event: **imperative** (calling the event
directly) and **event-oriented** (using `send()`).

The imperative style calls the event as a method:

```py
>>> machine = TrafficLightMachine()

>>> machine.cycle()
'Running Loop from green to yellow'

>>> [s.id for s in machine.configuration]
['yellow']

```

The event-oriented style uses {func}`send() <StateChart.send>`, which is
useful for dispatching events dynamically (e.g., from external input):

```py
>>> machine.send("cycle")
'Running Loop from yellow to red'

>>> [s.id for s in machine.configuration]
['red']

```

Both styles trigger the same processing pipeline:

1. Check the current state
2. Evaluate {ref}`guard conditions <validators and guards>`
3. Execute {ref}`actions` on the transition and states
4. Update the current state

```py
>>> [s.id for s in machine.configuration]
['red']

>>> machine.cycle()
'Running Loop from red to green'

>>> [s.id for s in machine.configuration]
['green']

```

```{seealso}
See {ref}`actions` and {ref}`validators and guards` for what happens during
each step of the processing pipeline.
```


## `send()` vs `raise_()`

{func}`send() <StateChart.send>` places events on the **external queue** — they
are processed after the current macrostep completes.

{func}`raise_() <StateChart.raise_>` places events on the **internal queue** —
they are processed **within** the current macrostep, before any pending external
events.

Use `raise_()` inside callbacks when you want the event handled as part of the
current processing cycle:

```py
>>> from statemachine import State, StateChart

>>> class TwoStepChart(StateChart):
...     idle = State("Idle", initial=True)
...     step1 = State("Step 1")
...     step2 = State("Step 2")
...
...     start = idle.to(step1)
...     advance = step1.to(step2)
...     reset = step2.to(idle)
...
...     def on_enter_step1(self):
...         self.raise_("advance")  # processed before the macrostep ends
...
...     def on_enter_step2(self):
...         self.raise_("reset")

>>> sm = TwoStepChart()
>>> sm.send("start")
>>> [s.id for s in sm.configuration]
['idle']

```

All three transitions (`start → advance → reset`) execute within a single
macrostep.

```{seealso}
See {ref}`macrostep-microstep` for the full processing model and
{ref}`error-execution` for using `raise_()` in error recovery patterns.
```


(delayed-events)=

## Delayed events

```{versionadded} 3.0.0
```

Events can be scheduled to fire after a delay (in milliseconds) using the
`delay` parameter on `send()`:

```python
# Fire after 500ms
sm.send("light_beacons", delay=500)

# Define delay directly on the Event
light = Event(dark.to(lit), delay=100)
```

Delayed events remain in the queue until their execution time arrives. They
can be cancelled before firing by providing a `send_id` and calling
`cancel_event()`:

```python
sm.send("light_beacons", delay=5000, send_id="beacon_signal")
sm.cancel_event("beacon_signal")  # removed from queue
```


(done-state-events)=

## `done.state` events

```{versionadded} 3.0.0
```

When a {ref}`compound state's <compound-states>` final child is entered, the
engine automatically queues a `done.state.{parent_id}` internal event. You
can define transitions for this event to react when a compound's work is
complete:

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

### `done.state` in parallel states

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

### DoneData

Final states can carry data to their `done.state` handlers via the `donedata`
parameter. The `donedata` value should be a callable (or method name string)
that returns a `dict`. The returned dict is passed as keyword arguments to the
`done.state` transition handler:

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
`donedata` can only be specified on `final=True` states. Attempting to use it on a
non-final state raises `InvalidDefinition`.
```


(done-state-convention)=

### The `done_state_` naming convention

Since Python identifiers cannot contain dots, the library provides a naming
convention: any event attribute starting with `done_state_` automatically
matches both the underscore form and the dot-notation form.

Unlike the `error_` convention (which replaces all underscores with dots),
`done_state_` only replaces the prefix, keeping the suffix unchanged. This
ensures that multi-word state names are preserved correctly:

| Attribute name                | Matches                                           |
|-------------------------------|---------------------------------------------------|
| `done_state_quest`            | `"done_state_quest"` and `"done.state.quest"`     |
| `done_state_lonely_mountain`  | `"done_state_lonely_mountain"` and `"done.state.lonely_mountain"` |

```py
>>> from statemachine import State, StateChart

>>> class QuestForErebor(StateChart):
...     class lonely_mountain(State.Compound):
...         approach = State(initial=True)
...         inside = State(final=True)
...         enter_mountain = approach.to(inside)
...     victory = State(final=True)
...     done_state_lonely_mountain = lonely_mountain.to(victory)

>>> sm = QuestForErebor()
>>> sm.send("enter_mountain")
>>> set(sm.configuration_values) == {"victory"}
True

```

The convention works with bare transitions, `TransitionList`, and `Event` objects
without an explicit `id`:

```py
>>> from statemachine import Event, State, StateChart

>>> class QuestWithEvent(StateChart):
...     class quest(State.Compound):
...         traveling = State(initial=True)
...         arrived = State(final=True)
...         finish = traveling.to(arrived)
...     celebration = State(final=True)
...     done_state_quest = Event(quest.to(celebration))

>>> sm = QuestWithEvent()
>>> sm.send("finish")
>>> set(sm.configuration_values) == {"celebration"}
True

```

```{note}
If you provide an explicit `id=` parameter, it takes precedence and the naming
convention is not applied.
```


## Error events

When a callback raises during a macrostep and {ref}`error_on_execution <error-execution>` is enabled,
the engine dispatches an `error.execution` internal event. You can define
transitions for this event to recover from errors within the statechart itself.

Since Python identifiers cannot contain dots, the library provides the `error_`
prefix naming convention: any event attribute starting with `error_` automatically
matches both the underscore form and the dot-notation form. For example,
`error_execution` matches both `"error_execution"` and `"error.execution"`.

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
