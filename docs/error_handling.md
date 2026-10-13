
(error-handling)=
# Error handling

```{seealso}
New to statecharts? See [](concepts.md) for an overview of how states,
transitions, events, and actions fit together.
```

What happens when a callback raises an exception during a transition?

With `StateChart`, errors in actions are caught by the engine and dispatched
as `error.execution` internal events — so the machine itself can react to
failures by transitioning to an error state, retrying, or recovering. This
follows the [SCXML error handling specification](https://www.w3.org/TR/scxml/#errorsAndEvents).

```{tip}
`catch_errors_as_events` is a class attribute that controls this behavior.
`StateChart` uses `True` by default (SCXML-compliant); set it to `False`
to let exceptions propagate to the caller instead. See {ref}`behaviour`
for the full comparison of behavioral attributes and how to customize them.
```


(error-execution)=

## How errors are caught

When an action raises during a {ref}`microstep <macrostep-microstep>`, the
engine catches the exception at the **block level**. Each phase of the
microstep is an independent block:

| Block | Callbacks |
|---|---|
| Exit | `on_exit_state()`, `on_exit_<state>()` |
| On | `on_transition()`, `on_<event>()` |
| Enter | `on_enter_state()`, `on_enter_<state>()` |

An error in one block:

- **Stops remaining actions in that block** — per the SCXML spec, execution
  MUST NOT continue within the same block after an error.
- **Does not affect other blocks** — subsequent phases of the microstep
  still execute. In particular, **`after` callbacks always run** regardless
  of errors in earlier blocks.

This means that even if a transition's `on` action raises, the target states
are still entered and `after_<event>()` callbacks still run. The error is
caught and queued as an `error.execution` internal event that fires within
the same {ref}`macrostep <macrostep-microstep>`.

```{note}
`before` callbacks run before any state changes, so an error in `before`
prevents the transition from executing — but `after` still runs because
it belongs to a separate block.
```


## The `error.execution` event

After catching an error, the engine places an `error.execution` event on the
internal queue. You can define transitions for this event to handle errors
within the state machine itself — transitioning to error states, logging, or
recovering.

### The `error_` naming convention

Since Python identifiers cannot contain dots, any event attribute starting
with `error_` automatically matches both the underscore and dot-notation
forms. For example, `error_execution` matches both `"error_execution"` and
`"error.execution"`:

```py
>>> from statemachine import State, StateChart

>>> class ResilientChart(StateChart):
...     operational = State(initial=True)
...     broken = State(final=True)
...
...     do_work = operational.to(operational, on="risky_action")
...     error_execution = operational.to(broken)
...
...     def risky_action(self):
...         raise RuntimeError("something went wrong")

>>> sm = ResilientChart()
>>> sm.send("do_work")
>>> "broken" in sm.configuration_values
True

```

```{note}
If you provide an explicit `id=` parameter on the `Event`, it takes
precedence and the naming convention is not applied.
```

### Accessing error data

The original exception is available as `error` in the keyword arguments
of callbacks on the `error.execution` transition. Use
{ref}`dependency injection <dependency-injection>` to receive it:

```py
>>> from statemachine import State, StateChart

>>> class ErrorLogger(StateChart):
...     running = State(initial=True)
...     failed = State(final=True)
...
...     process = running.to(running, on="do_process")
...     error_execution = running.to(failed, on="log_error")
...
...     def do_process(self):
...         raise ValueError("bad data")
...
...     def log_error(self, error):
...         self.last_error = error

>>> sm = ErrorLogger()
>>> sm.send("process")
>>> str(sm.last_error)
'bad data'

```


(error-in-error-handler)=

### Error in error handler

If the `error.execution` handler itself raises, the engine **ignores** the
second error (logging a warning) to prevent infinite loops. The machine
remains in whatever configuration it reached before the failed handler.

```{note}
During `error.execution` processing, errors in transition `on` content
are **not** caught at block level — they propagate to the microstep where
they are silently discarded. This prevents infinite loops when an error
handler's own action raises (e.g., a self-transition
`error_execution = s1.to(s1, on="handler")` where `handler` raises).
Entry/exit blocks still use block-level catching regardless of the
current event.
```


(platform-events)=

## Platform events are not meant to be sent by user code

`error.execution` is a **platform event**: the engine raises it after catching
an error, and that is the only way it is meant to occur. The same holds for
the other events the engine generates, such as `done.state.<id>` and
`done.invoke.<id>`, described in {ref}`done-state-events`. SCXML defines these
names for events the processor generates and gives them no external
counterpart, so a `send("error.execution")` coming from user code has no
meaning in the specification.

The library does not enforce this. It makes no distinction between platform
events and user events, so a transition declared for `error.execution` is
listed by `allowed_events` and `enabled_events()` like any other, and `send()`
accepts it:

```py
>>> from statemachine import Event, State, StateChart

>>> class Reporter(StateChart):
...     running = State(initial=True)
...     failed = State(final=True)
...
...     process = running.to(running, on="do_process")
...     error_execution = Event(running.to(failed, on="log_error"), id="error.execution")
...
...     def do_process(self):
...         raise ValueError("bad data")
...
...     def log_error(self, error):
...         self.last_error = error

>>> sm = Reporter()
>>> [e.id for e in sm.allowed_events]
['process', 'error.execution']
>>> [e.id for e in sm.enabled_events()]
['process', 'error.execution']

```

Sending it yourself bypasses the error-handling contract. A bare
`send("error.execution")` carries no exception, so a handler that asks for
`error` fails. With `catch_errors_as_events` enabled, the `StateChart`
default, that failure is discarded with a logged warning, the same guard
described in {ref}`error-in-error-handler`, and the configuration is
unchanged (exit actions that ran before the failure are not undone, and
`after` callbacks do not run). With `catch_errors_as_events=False` the
failure propagates to the caller instead:

```py
>>> sm.send("error.execution")
>>> "running" in sm.configuration_values
True
>>> hasattr(sm, "last_error")
False

```

Nothing stops user code from supplying the argument either. A
`send("error.execution", error=exc)` runs the handler with `exc` and completes
the transition, although no action failed. Raised by the engine, the same
transition receives the real exception:

```py
>>> sm.send("process")
>>> "failed" in sm.configuration_values
True
>>> str(sm.last_error)
'bad data'

```

Treat these events as the engine's: declare transitions that react to them,
and skip them when you offer the events from `allowed_events` or
`enabled_events()` to the outside, for example in a UI or an API. The ids
the engine generates share the `error.` and `done.` prefixes, and a transition
declared with the `error_`, `done_state_` or `done_invoke_` convention also
answers to the underscore spelling, so filter both:

```py
>>> sm = Reporter()
>>> [e.id for e in sm.allowed_events if not e.id.startswith(("error", "done"))]
['process']

```

To trigger a failure path from user code, raise the exception inside an
action, or declare a regular event of your own.


(error-handling-cleanup-finalize)=

## Cleanup / finalize pattern

A common need is to run cleanup code after a transition **regardless of
success or failure** — releasing a lock, closing a connection, or clearing
temporary state.

Because errors are caught at the block level, `after_<event>()` callbacks
always run — making them a natural **finalize** hook, similar to Python's
`try/finally`:

```py
>>> from statemachine import Event, State, StateChart

>>> class ResourceManager(StateChart):
...     idle = State(initial=True)
...     working = State()
...     recovering = State()
...
...     start = idle.to(working)
...     done = working.to(idle)
...     recover = recovering.to(idle)
...     error_execution = Event(working.to(recovering), id="error.execution")
...
...     def __init__(self, should_fail=False):
...         self.should_fail = should_fail
...         self.released = False
...         super().__init__()
...
...     def on_enter_working(self):
...         if self.should_fail:
...             raise RuntimeError("something went wrong")
...         self.raise_("done")
...
...     def after_start(self):
...         self.released = True  # always runs — finalize hook
...
...     def on_enter_recovering(self, error):
...         self.last_error = error
...         self.raise_("recover")

```

On the **success** path, the machine transitions `idle → working → idle`
and `after_start` releases the resource:

```py
>>> sm = ResourceManager(should_fail=False)
>>> sm.send("start")
>>> "idle" in sm.configuration_values
True
>>> sm.released
True

```

On the **failure** path, the action raises, but `after_start` **still runs**.
Then `error.execution` fires, transitions to `recovering`, and auto-recovers
back to `idle`:

```py
>>> sm = ResourceManager(should_fail=True)
>>> sm.send("start")
>>> "idle" in sm.configuration_values
True
>>> sm.released  # finalize ran despite the error
True
>>> str(sm.last_error)
'something went wrong'

```

```{seealso}
See {ref}`sphx_glr_auto_examples_statechart_cleanup_machine.py` for a
more detailed version of this pattern with annotated output.
```


## Validators do not trigger error events

{ref}`Validators <validators>` operate in the **transition-selection** phase,
before any state changes occur. Their exceptions **always propagate** to the
caller — they are never caught by the engine and never converted to
`error.execution` events, regardless of the `catch_errors_as_events` setting.

This is intentional: a validator rejection means the transition should not
happen at all. It is semantically equivalent to a condition returning
`False`, but communicates the reason via an exception.

```{seealso}
See {ref}`validators` for examples and the full semantics of validator
propagation.
```


```{seealso}
See {ref}`behaviour` for the full comparison of behavioral attributes
and how to customize `catch_errors_as_events` and other settings.
See {ref}`actions` for the callback execution order within each
microstep.
```
