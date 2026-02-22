
(error-handling)=
# Error handling

When callbacks raise exceptions during a transition, the state machine needs
a strategy. This library supports two models: **exception propagation** (the
traditional approach) and **error events** (the SCXML-compliant approach).

## Two models

| Approach              | `error_on_execution` | Behavior                                              |
|-----------------------|----------------------|-------------------------------------------------------|
| Exception propagation | `False`              | Exceptions bubble up to the caller like normal Python. |
| Error events          | `True`               | Exceptions are caught and dispatched as `error.execution` internal events. |

`StateChart` uses `error_on_execution = True` by default — the SCXML-compliant
behavior. You can switch to exception propagation by overriding the attribute:

```python
from statemachine import StateChart

class MyChart(StateChart):
    error_on_execution = False  # exceptions propagate to the caller
```

### When to use which

**Exception propagation** (`error_on_execution = False`) is simpler and
familiar to most Python developers. It works well for flat state machines
where errors should stop execution immediately and be handled by the caller
with `try/except`.

**Error events** (`error_on_execution = True`) are the SCXML standard and
the recommended approach for statecharts. They allow the machine to handle
errors as part of its own logic — transitioning to error states, retrying,
or recovering — without leaking implementation details to the caller. This
is especially powerful in hierarchical machines where different states may
handle errors differently.


(error-execution)=
## Error events with `error.execution`

When `error_on_execution` is `True`, runtime exceptions during transitions
are caught by the engine and result in an internal `error.execution` event
being placed on the queue. This follows the
[SCXML error handling specification](https://www.w3.org/TR/scxml/#errorsAndEvents).

You can define transitions for this event to gracefully handle errors within
the state machine itself.

### The `error_` naming convention

Since Python identifiers cannot contain dots, the library provides a naming
convention: any event attribute starting with `error_` automatically matches
both the underscore form and the dot-notation form. For example,
`error_execution` matches both `"error_execution"` and `"error.execution"`.

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

The convention works with both bare transitions and `Event` objects without
an explicit `id`:

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
If you provide an explicit `id=` parameter, it takes precedence and the naming
convention is not applied.
```

### Accessing error data

The error object is passed as `error` in the keyword arguments to callbacks
on the `error.execution` transition:

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


### Error-in-error-handler behavior

If an error occurs while processing the `error.execution` event itself, the
engine ignores the second error (logging a warning) to prevent infinite loops.
The state machine remains in the configuration it was in before the failed
error handler.


## Block-level error catching

`StateChart` catches errors at the **block level**, not the microstep level.
Each phase of the microstep — `on_exit`, transition `on` content, `on_enter`
— is an independent block. An error in one block:

- **Stops remaining actions in that block** (per SCXML spec, execution MUST
  NOT continue within the same block after an error).
- **Does not affect other blocks** — subsequent phases of the microstep still
  execute. In particular, `after` callbacks always run regardless of errors
  in earlier blocks.

This means that even if a transition's `on` action raises an exception, the
transition completes: target states are entered and `after_<event>()` callbacks
still run. The error is caught and queued as an `error.execution` internal
event, which can be handled by a separate transition.

```{note}
During `error.execution` processing, errors in transition `on` content are
**not** caught at block level — they propagate to the microstep, where they
are silently ignored. This prevents infinite loops when an error handler's own
action raises (e.g., a self-transition `error_execution = s1.to(s1, on="handler")`
where `handler` raises). Entry/exit blocks always use block-level error
catching regardless of the current event.
```


(error-handling-cleanup-finalize)=
## Cleanup / finalize pattern

A common need is to run cleanup code after a transition **regardless of
success or failure** — for example, releasing a lock or closing a resource.

Because `StateChart` catches errors at the block level (see above),
`after_<event>()` callbacks still run even when an action raises an exception.
This makes `after_<event>()` a natural **finalize** hook — no need to
duplicate cleanup logic in an error handler.

For error-specific handling (logging, recovery), define an `error.execution`
transition and use {func}`raise_() <StateChart.raise_>` to auto-recover
within the same macrostep.

See the full working example in {ref}`sphx_glr_auto_examples_statechart_cleanup_machine.py`.


```{seealso}
See {ref}`behaviour` for the full comparison of `StateChart` behavioral
attributes and how to customize them.
```
