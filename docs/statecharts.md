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
