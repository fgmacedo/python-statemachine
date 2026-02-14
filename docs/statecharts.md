(statecharts)=
# Statecharts

Statecharts are a powerful extension to state machines that add hierarchy and concurrency.
They extend the concept of state machines by introducing **compound states** (states with
inner substates) and **parallel states** (states that can be active simultaneously).

This library's statechart support follows the
[SCXML specification](https://www.w3.org/TR/scxml/), a W3C standard for statechart notation.

## StateChart vs StateMachine

The `StateChart` class is the new base class that follows the
[SCXML specification](https://www.w3.org/TR/scxml/). The `StateMachine` class extends
`StateChart` but overrides several defaults to preserve backward compatibility with
existing code.

The behavioral differences between the two classes are controlled by class-level
attributes. This design allows a gradual upgrade path: you can start from `StateMachine`
and selectively enable spec-compliant behaviors one at a time, or start from `StateChart`
and get full SCXML compliance out of the box.

```{tip}
We **strongly recommend** that new projects use `StateChart` directly. Existing projects
should consider migrating when possible, as the SCXML-compliant behavior is the standard
and provides more predictable semantics.
```

### Comparison table

| Attribute                          | `StateChart`  | `StateMachine` | Description                                      |
|------------------------------------|---------------|----------------|--------------------------------------------------|
| `allow_event_without_transition`   | `True`        | `False`        | Tolerate events that don't match any transition   |
| `enable_self_transition_entries`   | `True`        | `False`        | Execute entry/exit actions on self-transitions    |
| `atomic_configuration_update`      | `False`       | `True`         | When to update configuration during a microstep   |
| `error_on_execution`              | `True`        | `False`        | Catch runtime errors as `error.execution` events  |

### `allow_event_without_transition`

When `True` (SCXML default), sending an event that does not match any enabled transition
is silently ignored. When `False` (legacy default), a `TransitionNotAllowed` exception is
raised, including for unknown event names.

The SCXML spec requires tolerance to unmatched events, as the event-driven model expects
that not every event is relevant in every state.

### `enable_self_transition_entries`

When `True` (SCXML default), a self-transition (a transition where the source and target
are the same state) will execute the state's exit and entry actions, just like any other
transition. When `False` (legacy default), self-transitions skip entry/exit actions.

The SCXML spec treats self-transitions as regular transitions that happen to return to the
same state, so entry/exit actions must fire.

### `atomic_configuration_update`

When `False` (SCXML default), a microstep follows the SCXML processing order: first exit
all states in the exit set (running exit callbacks), then execute the transition content
(`on` callbacks), then enter all states in the entry set (running entry callbacks). During
the `on` callbacks, the configuration may be empty or partial.

When `True` (legacy default), the configuration is updated atomically after the `on`
callbacks, so `sm.configuration` and `state.is_active` always reflect a consistent snapshot
during the transition. This was the behavior of all previous versions.

```{note}
When `atomic_configuration_update` is `False`, `on` callbacks can request
`previous_configuration` and `new_configuration` keyword arguments to inspect which states
were active before and after the microstep.
```

### `error_on_execution`

When `True` (SCXML default), runtime exceptions in callbacks (guards, actions, entry/exit)
are caught by the engine and result in an internal `error.execution` event. When `False`
(legacy default), exceptions propagate normally to the caller.

See {ref}`error-execution` below for full details.

### Gradual migration

You can override any of these attributes individually. For example, to adopt SCXML error
handling in an existing `StateMachine` without changing other behaviors:

```python
class MyMachine(StateMachine):
    error_on_execution = True
    # ... everything else behaves as before ...
```

Or to use `StateChart` but keep the legacy atomic configuration update:

```python
class MyChart(StateChart):
    atomic_configuration_update = True
    # ... SCXML-compliant otherwise ...
```

(error-execution)=
## Error handling with `error.execution`

As described above, when `error_on_execution` is `True`, runtime exceptions during
transitions are caught by the engine and result in an internal `error.execution` event
being placed on the queue. This follows the
[SCXML error handling specification](https://www.w3.org/TR/scxml/#errorsAndEvents).

You can define transitions for this event to gracefully handle errors within the state
machine itself.

### The `error_` naming convention

Since Python identifiers cannot contain dots, the library provides a naming convention:
any event attribute starting with `error_` automatically matches both the underscore form
and the dot-notation form. For example, `error_execution` matches both `"error_execution"`
and `"error.execution"`.

```py
>>> from statemachine import State, StateChart

>>> class MyChart(StateChart):
...     s1 = State("s1", initial=True)
...     error_state = State("error_state", final=True)
...
...     go = s1.to(s1, on="bad_action")
...     error_execution = s1.to(error_state)
...
...     def bad_action(self):
...         raise RuntimeError("something went wrong")

>>> sm = MyChart()
>>> sm.send("go")
>>> sm.configuration == {sm.error_state}
True

```

This is equivalent to the more verbose explicit form:

```python
error_execution = Event(s1.to(error_state), id="error.execution")
```

The convention works with both bare transitions and `Event` objects without an explicit `id`:

```py
>>> from statemachine import Event, State, StateChart

>>> class ChartWithEvent(StateChart):
...     s1 = State("s1", initial=True)
...     error_state = State("error_state", final=True)
...
...     go = s1.to(s1, on="bad_action")
...     error_execution = Event(s1.to(error_state))
...
...     def bad_action(self):
...         raise RuntimeError("something went wrong")

>>> sm = ChartWithEvent()
>>> sm.send("go")
>>> sm.configuration == {sm.error_state}
True

```

```{note}
If you provide an explicit `id=` parameter, it takes precedence and the naming convention
is not applied.
```

### Accessing error data

The error object is passed as `error` in the keyword arguments to callbacks on the
`error.execution` transition:

```py
>>> from statemachine import State, StateChart

>>> class ErrorDataChart(StateChart):
...     s1 = State("s1", initial=True)
...     error_state = State("error_state", final=True)
...
...     go = s1.to(s1, on="bad_action")
...     error_execution = s1.to(error_state, on="handle_error")
...
...     def bad_action(self):
...         raise RuntimeError("specific error")
...
...     def handle_error(self, error=None, **kwargs):
...         self.last_error = error

>>> sm = ErrorDataChart()
>>> sm.send("go")
>>> str(sm.last_error)
'specific error'

```

### Enabling in StateMachine

By default, `StateMachine` propagates exceptions (`error_on_execution = False`). You can
enable `error.execution` handling as described in {ref}`gradual migration <statecharts>`:

```python
class MyMachine(StateMachine):
    error_on_execution = True
    # ... define states, transitions, error_execution handler ...
```

### Error-in-error-handler behavior

If an error occurs while processing the `error.execution` event itself, the engine
ignores the second error (logging a warning) to prevent infinite loops. The state machine
remains in the configuration it was in before the failed error handler.

(compound-states)=
## Compound states

Compound states contain inner child states. They allow you to break down complex
behavior into hierarchical levels. When a compound state is entered, its `initial`
child is automatically activated along with the parent.

Use the `State.Compound` inner class syntax to define compound states in Python:

```py
>>> from statemachine import State, StateChart

>>> class ShireToRoad(StateChart):
...     class shire(State.Compound):
...         bag_end = State(initial=True)
...         green_dragon = State()
...         visit_pub = bag_end.to(green_dragon)
...
...     road = State(final=True)
...     depart = shire.to(road)

>>> sm = ShireToRoad()
>>> set(sm.configuration_values) == {"shire", "bag_end"}
True

```

When entering the `shire` compound state, both `shire` (the parent) and `bag_end`
(the initial child) become active. Transitions within a compound change the active
child while the parent stays active:

```py
>>> sm.send("visit_pub")
>>> "shire" in sm.configuration_values and "green_dragon" in sm.configuration_values
True

```

Exiting a compound removes the parent **and** all its descendants:

```py
>>> sm.send("depart")
>>> set(sm.configuration_values) == {"road"}
True

```

Compound states can be nested to any depth:

```py
>>> from statemachine import State, StateChart

>>> class MoriaExpedition(StateChart):
...     class moria(State.Compound):
...         class upper_halls(State.Compound):
...             entrance = State(initial=True)
...             bridge = State(final=True)
...             cross = entrance.to(bridge)
...         assert isinstance(upper_halls, State)
...         depths = State(final=True)
...         descend = upper_halls.to(depths)

>>> sm = MoriaExpedition()
>>> set(sm.configuration_values) == {"moria", "upper_halls", "entrance"}
True

```

```{note}
Inside a `State.Compound` class body, the class name itself becomes a `State`
instance after the metaclass processes it. The `assert isinstance(upper_halls, State)`
in the example above demonstrates this.
```

### `done.state` events

When a final child of a compound state is entered, the engine automatically queues
a `done.state.{parent_id}` internal event. You can define transitions for this
event to react when a compound's work is complete:

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

The `done_state_` naming convention (described below) automatically registers
`done_state_quest` as matching the `done.state.quest` event.

(parallel-states)=
## Parallel states

Parallel states activate **all** child regions simultaneously. Each region operates
independently — events in one region don't affect others. Use `State.Parallel`:

```py
>>> from statemachine import State, StateChart

>>> class WarOfTheRing(StateChart):
...     validate_disconnected_states = False
...     class war(State.Parallel):
...         class frodos_quest(State.Compound):
...             shire = State(initial=True)
...             mordor = State(final=True)
...             journey = shire.to(mordor)
...         class aragorns_path(State.Compound):
...             ranger = State(initial=True)
...             king = State(final=True)
...             coronation = ranger.to(king)

>>> sm = WarOfTheRing()
>>> config = set(sm.configuration_values)
>>> all(s in config for s in ("war", "frodos_quest", "shire", "aragorns_path", "ranger"))
True

```

Events in one region leave others unchanged:

```py
>>> sm.send("journey")
>>> "mordor" in sm.configuration_values and "ranger" in sm.configuration_values
True

```

A `done.state.{parent_id}` event fires only when **all** regions of the parallel
state have reached a final state:

```py
>>> from statemachine import State, StateChart

>>> class WarWithDone(StateChart):
...     validate_disconnected_states = False
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

```{note}
Parallel states commonly require `validate_disconnected_states = False` because
regions may not be reachable from each other via transitions.
```

(history-states)=
## History pseudo-states

A history pseudo-state records the active configuration of a compound state when it
is exited. Re-entering the compound via the history state restores the previously
active child instead of starting from the initial child.

Import `HistoryState` and place it inside a `State.Compound`:

```py
>>> from statemachine import HistoryState, State, StateChart

>>> class GollumPersonality(StateChart):
...     validate_disconnected_states = False
...     class personality(State.Compound):
...         smeagol = State(initial=True)
...         gollum = State()
...         h = HistoryState()
...         dark_side = smeagol.to(gollum)
...         light_side = gollum.to(smeagol)
...     outside = State()
...     leave = personality.to(outside)
...     return_via_history = outside.to(personality.h)

>>> sm = GollumPersonality()
>>> sm.send("dark_side")
>>> "gollum" in sm.configuration_values
True

>>> sm.send("leave")
>>> set(sm.configuration_values) == {"outside"}
True

>>> sm.send("return_via_history")
>>> "gollum" in sm.configuration_values
True

```

### Shallow vs deep history

By default, `HistoryState()` uses **shallow** history: it remembers only the direct
child of the compound. If the remembered child is itself a compound, it re-enters
from its initial state.

Use `HistoryState(deep=True)` for **deep** history, which remembers the exact leaf
state and restores the full hierarchy:

```py
>>> from statemachine import HistoryState, State, StateChart

>>> class DeepMemoryOfMoria(StateChart):
...     validate_disconnected_states = False
...     class moria(State.Compound):
...         class halls(State.Compound):
...             entrance = State(initial=True)
...             chamber = State()
...             explore = entrance.to(chamber)
...         assert isinstance(halls, State)
...         h = HistoryState(deep=True)
...         bridge = State(final=True)
...         flee = halls.to(bridge)
...     outside = State()
...     escape = moria.to(outside)
...     return_deep = outside.to(moria.h)

>>> sm = DeepMemoryOfMoria()
>>> sm.send("explore")
>>> "chamber" in sm.configuration_values
True

>>> sm.send("escape")
>>> set(sm.configuration_values) == {"outside"}
True

>>> sm.send("return_deep")
>>> "chamber" in sm.configuration_values and "halls" in sm.configuration_values
True

```

### Default transitions

You can define a default transition from a history state. This is used when
the compound has never been visited before (no history recorded):

```python
class MyChart(StateChart):
    class compound(State.Compound):
        a = State(initial=True)
        b = State()
        h = HistoryState()
        _ = h.to(a)  # default: enter 'a' if no history
```

(eventless-transitions)=
## Eventless transitions

Eventless transitions have no event trigger — they fire automatically when their
guard condition is met. If no guard is specified, they fire immediately (unconditional).

```py
>>> from statemachine import State, StateChart

>>> class BeaconChain(StateChart):
...     class beacons(State.Compound):
...         first = State(initial=True)
...         second = State()
...         last = State(final=True)
...         first.to(second)
...         second.to(last)
...     signal_received = State(final=True)
...     done_state_beacons = beacons.to(signal_received)

>>> sm = BeaconChain()
>>> set(sm.configuration_values) == {"signal_received"}
True

```

Unconditional eventless chains cascade in a single macrostep. With a guard condition,
the transition fires after any event processing when the guard evaluates to `True`:

```py
>>> from statemachine import State, StateChart

>>> class RingCorruption(StateChart):
...     resisting = State(initial=True)
...     corrupted = State(final=True)
...     resisting.to(corrupted, cond="is_corrupted")
...     bear_ring = resisting.to.itself(internal=True, on="increase_power")
...     ring_power = 0
...     def is_corrupted(self):
...         return self.ring_power > 5
...     def increase_power(self):
...         self.ring_power += 2

>>> sm = RingCorruption()
>>> sm.send("bear_ring")
>>> sm.send("bear_ring")
>>> "resisting" in sm.configuration_values
True

>>> sm.send("bear_ring")
>>> "corrupted" in sm.configuration_values
True

```

(donedata)=
## DoneData

Final states can carry data to their `done.state` handlers via the `donedata` parameter.
The `donedata` value should be a callable (or method name string) that returns a `dict`.
The returned dict is passed as keyword arguments to the `done.state` transition handler:

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
## The `done_state_` naming convention

Since Python identifiers cannot contain dots, the library provides a naming convention
for `done.state` events: any event attribute starting with `done_state_` automatically
matches both the underscore form and the dot-notation form.

Unlike the `error_` convention (which replaces all underscores with dots), `done_state_`
only replaces the prefix, keeping the suffix unchanged. This ensures that multi-word
state names are preserved correctly:

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
If you provide an explicit `id=` parameter, it takes precedence and the naming convention
is not applied.
```

(delayed-events)=
## Delayed events

Events can be scheduled to fire after a delay (in milliseconds) using the `delay`
parameter on `send()`:

```python
# Fire after 500ms
sm.send("light_beacons", delay=500)

# Define delay directly on the Event
light = Event(dark.to(lit), delay=100)
```

Delayed events remain in the queue until their execution time arrives. They can be
cancelled before firing by providing an `event_id` and calling `cancel_event()`:

```python
sm.send("light_beacons", delay=5000, event_id="beacon_signal")
sm.cancel_event("beacon_signal")  # removed from queue
```

(in-conditions)=
## `In()` conditions

The `In()` function can be used in condition expressions to check whether a state is
currently active. This is especially useful for cross-region guards in parallel states:

```py
>>> from statemachine import State, StateChart

>>> class CoordinatedAdvance(StateChart):
...     validate_disconnected_states = False
...     class forces(State.Parallel):
...         class vanguard(State.Compound):
...             waiting = State(initial=True)
...             advanced = State(final=True)
...             move_forward = waiting.to(advanced)
...         class rearguard(State.Compound):
...             holding = State(initial=True)
...             moved_up = State(final=True)
...             holding.to(moved_up, cond="In('advanced')")

>>> sm = CoordinatedAdvance()
>>> "waiting" in sm.configuration_values and "holding" in sm.configuration_values
True

>>> sm.send("move_forward")
>>> "advanced" in sm.configuration_values and "moved_up" in sm.configuration_values
True

```

The rearguard's eventless transition only fires when the vanguard's `advanced` state
is in the current configuration.
