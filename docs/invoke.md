(invoke)=
# Invoke

Invoke lets a state spawn external work — API calls, file I/O, child state machines —
when it is entered, and automatically cancel that work when the state is exited. This
follows the [SCXML `<invoke>` semantics](https://www.w3.org/TR/scxml/#invoke) and is
similar to the **do activity** (`do/`) concept in UML Statecharts — an ongoing behavior
that runs for the duration of a state and is cancelled when the state is exited.

## Execution model

Invoke handlers run **outside** the main state machine processing loop:

- **Sync engine**: each invoke handler runs in a **daemon thread**.
- **Async engine**: each invoke handler runs in a **thread executor**
  (`loop.run_in_executor`), wrapped in an `asyncio.Task`. The executor is used because
  invoke handlers are expected to perform blocking I/O (network calls, file access,
  subprocess communication) that would freeze the event loop if run directly.

When a handler completes, a `done.invoke.<state>.<id>` event is automatically sent back
to the machine. If the handler raises an exception, an `error.execution` event is sent
instead. If the owning state is exited before the handler finishes, the invocation is
**cancelled** — `ctx.cancelled` is set and `on_cancel()` is called on `IInvoke` handlers.

## Callback group

Invoke is a first-class callback group, just like `enter` and `exit`. This means
convention naming (`on_invoke_<state>`), decorators (`@state.invoke`), inline callables,
and the full {ref}`SignatureAdapter <actions>` dependency injection all work out of the box.

## Quick start

The simplest invoke is a plain callable passed to the `invoke` parameter. Here we read a
config file in a background thread and transition to `ready` when the data is available:

```py
>>> import json
>>> import tempfile
>>> import time
>>> from pathlib import Path
>>> from statemachine import State, StateChart

>>> config_file = Path(tempfile.mktemp(suffix=".json"))
>>> _ = config_file.write_text('{"db_host": "localhost", "db_port": 5432}')

>>> def load_config():
...     return json.loads(config_file.read_text())

>>> class ConfigLoader(StateChart):
...     loading = State(initial=True, invoke=load_config)
...     ready = State(final=True)
...     done_invoke_loading = loading.to(ready)
...
...     def on_enter_ready(self, data=None, **kwargs):
...         self.config = data

>>> sm = ConfigLoader()
>>> time.sleep(0.2)

>>> "ready" in sm.configuration_values
True
>>> sm.config
{'db_host': 'localhost', 'db_port': 5432}

>>> config_file.unlink()

```

When `loading` is entered, `load_config()` runs in a background thread. When it returns,
a `done.invoke.loading.<id>` event is automatically sent to the machine, triggering
the `done_invoke_loading` transition. The return value is available as the `data`
keyword argument in callbacks on the target state.

## Naming conventions

Like `on_enter_<state>` and `on_exit_<state>`, invoke supports naming conventions:

- `on_invoke_state` — generic, called for every state with invoke
- `on_invoke_<state_id>` — specific to a state

```py
>>> config_file = Path(tempfile.mktemp(suffix=".json"))
>>> _ = config_file.write_text('{"feature_flags": ["dark_mode", "beta_api"]}')

>>> class FeatureLoader(StateChart):
...     loading = State(initial=True)
...     ready = State(final=True)
...     done_invoke_loading = loading.to(ready)
...
...     def on_invoke_loading(self, **kwargs):
...         """Naming convention: on_invoke_<state_id>."""
...         return json.loads(config_file.read_text())
...
...     def on_enter_ready(self, data=None, **kwargs):
...         self.features = data

>>> sm = FeatureLoader()
>>> time.sleep(0.2)

>>> "ready" in sm.configuration_values
True
>>> sm.features["feature_flags"]
['dark_mode', 'beta_api']

>>> config_file.unlink()

```

## Decorator syntax

Use the `@state.invoke` decorator:

```py
>>> config_file = Path(tempfile.mktemp(suffix=".txt"))
>>> _ = config_file.write_text("line 1\nline 2\nline 3\n")

>>> class LineCounter(StateChart):
...     counting = State(initial=True)
...     done = State(final=True)
...     done_invoke_counting = counting.to(done)
...
...     @counting.invoke
...     def count_lines(self, **kwargs):
...         text = config_file.read_text()
...         return len(text.splitlines())
...
...     def on_enter_done(self, data=None, **kwargs):
...         self.total_lines = data

>>> sm = LineCounter()
>>> time.sleep(0.2)

>>> "done" in sm.configuration_values
True
>>> sm.total_lines
3

>>> config_file.unlink()

```

## `done.invoke` transitions

Use the `done_invoke_<state>` naming convention to declare transitions that fire when
an invoke handler completes:

```py
>>> config_file = Path(tempfile.mktemp(suffix=".json"))
>>> _ = config_file.write_text('{"version": "3.0.0"}')

>>> class VersionChecker(StateChart):
...     checking = State(initial=True, invoke=lambda: json.loads(config_file.read_text()))
...     checked = State(final=True)
...     done_invoke_checking = checking.to(checked)
...
...     def on_enter_checked(self, data=None, **kwargs):
...         self.version = data["version"]

>>> sm = VersionChecker()
>>> time.sleep(0.2)

>>> "checked" in sm.configuration_values
True
>>> sm.version
'3.0.0'

>>> config_file.unlink()

```

The `done_invoke_<state>` prefix maps to the `done.invoke.<state>` event family,
matching any invoke completion for that state regardless of the specific invoke ID.

## IInvoke protocol

For advanced use cases, implement the `IInvoke` protocol. This gives you access to
the `InvokeContext` — with the invoke ID, cancellation signal, event kwargs, and a
reference to the parent machine:

```py
>>> from statemachine.invoke import IInvoke, InvokeContext

>>> class FileReader:
...     """Reads a file and returns its content. Supports cancellation."""
...     def run(self, ctx: InvokeContext):
...         # ctx.invokeid — unique ID for this invocation
...         # ctx.state_id — the state that triggered invoke
...         # ctx.cancelled — threading.Event, set when state exits
...         # ctx.send — send events to parent machine
...         # ctx.machine — reference to parent machine
...         # ctx.kwargs — keyword arguments from the triggering event
...         path = ctx.machine.file_path
...         return Path(path).read_text()
...
...     def on_cancel(self):
...         pass  # cleanup resources if needed

>>> isinstance(FileReader(), IInvoke)
True

```

Pass a class to the `invoke` parameter — each state machine instance gets a fresh handler:

```py
>>> config_file = Path(tempfile.mktemp(suffix=".csv"))
>>> _ = config_file.write_text("name,age\nAlice,30\nBob,25\n")

>>> class CSVLoader(StateChart):
...     loading = State(initial=True, invoke=FileReader)
...     ready = State(final=True)
...     done_invoke_loading = loading.to(ready)
...
...     def __init__(self, file_path, **kwargs):
...         self.file_path = file_path
...         super().__init__(**kwargs)
...
...     def on_enter_ready(self, data=None, **kwargs):
...         self.content = data

>>> sm = CSVLoader(file_path=str(config_file))
>>> time.sleep(0.2)

>>> "ready" in sm.configuration_values
True
>>> sm.content
'name,age\nAlice,30\nBob,25\n'

>>> config_file.unlink()

```

## Cancellation

When a state with active invoke handlers is exited:

1. `ctx.cancelled` is set (a `threading.Event`) — handlers should poll this
2. `on_cancel()` is called on `IInvoke` handlers (if defined)
3. For the async engine, the asyncio Task is cancelled

Events from cancelled invocations are silently ignored.

```py
>>> cancel_called = []

>>> class SlowFileReader:
...     def run(self, ctx: InvokeContext):
...         ctx.cancelled.wait(timeout=5.0)
...
...     def on_cancel(self):
...         cancel_called.append(True)

>>> class CancelMachine(StateChart):
...     loading = State(initial=True, invoke=SlowFileReader)
...     stopped = State(final=True)
...     cancel = loading.to(stopped)

>>> sm = CancelMachine()
>>> time.sleep(0.05)
>>> sm.send("cancel")
>>> time.sleep(0.05)
>>> cancel_called
[True]

```

## Event data propagation

When a state with invoke handlers is entered via an event, the keyword arguments from
that event are forwarded to the invoke handlers. Plain callables receive them via
{ref}`SignatureAdapter <actions>` dependency injection; `IInvoke` handlers receive them
via `ctx.kwargs`:

```py
>>> config_file = Path(tempfile.mktemp(suffix=".json"))
>>> _ = config_file.write_text('{"debug": true}')

>>> class ConfigByName(StateChart):
...     idle = State(initial=True)
...     loading = State()
...     ready = State(final=True)
...     start = idle.to(loading)
...     done_invoke_loading = loading.to(ready)
...
...     def on_invoke_loading(self, file_name=None, **kwargs):
...         """file_name comes from send('start', file_name=...)."""
...         return json.loads(Path(file_name).read_text())
...
...     def on_enter_ready(self, data=None, **kwargs):
...         self.config = data

>>> sm = ConfigByName()
>>> sm.send("start", file_name=str(config_file))
>>> time.sleep(0.2)

>>> "ready" in sm.configuration_values
True
>>> sm.config
{'debug': True}

>>> config_file.unlink()

```

For initial states (entered automatically, not via an event), `kwargs` is empty.

## Error handling

If an invoke handler raises an exception, `error.execution` is sent to the machine's
internal queue (when `error_on_execution=True`, the default for `StateChart`). You can
handle it with a transition for `error.execution`:

```py
>>> class MissingFileLoader(StateChart):
...     loading = State(
...         initial=True,
...         invoke=lambda: Path("/tmp/nonexistent_file_12345.json").read_text(),
...     )
...     error_state = State(final=True)
...     error_execution = loading.to(error_state)
...
...     def on_enter_error_state(self, error=None, **kwargs):
...         self.error_type = type(error).__name__

>>> sm = MissingFileLoader()
>>> time.sleep(0.2)

>>> "error_state" in sm.configuration_values
True
>>> sm.error_type
'FileNotFoundError'

```

## Multiple invokes

### Independent invokes (one event each)

Pass a list to run multiple handlers concurrently. Each handler gets its own
`done.invoke.<state>.<id>` event — the **first** one to complete triggers the
`done_invoke_<state>` transition (the remaining events are ignored if the state
was already exited):

```py
>>> file_a = Path(tempfile.mktemp(suffix=".txt"))
>>> file_b = Path(tempfile.mktemp(suffix=".txt"))
>>> _ = file_a.write_text("hello")
>>> _ = file_b.write_text("world")

>>> class MultiLoader(StateChart):
...     loading = State(
...         initial=True,
...         invoke=[lambda: file_a.read_text(), lambda: file_b.read_text()],
...     )
...     ready = State(final=True)
...     done_invoke_loading = loading.to(ready)

>>> sm = MultiLoader()
>>> time.sleep(0.2)

>>> "ready" in sm.configuration_values
True

>>> file_a.unlink()
>>> file_b.unlink()

```

This follows the [SCXML spec](https://www.w3.org/TR/scxml/#invoke): each `<invoke>`
is independent and generates its own completion event. Use this when you only need
**any one** of the handlers to complete, or when each invoke is handled by a
separate transition.

### Grouped invokes (wait for all)

Use {func}`~statemachine.invoke.invoke_group` to run multiple callables concurrently
and wait for **all** of them to complete before sending a single `done.invoke` event.
The `data` is a list of results in the same order as the input callables:

```py
>>> from statemachine.invoke import invoke_group

>>> file_a = Path(tempfile.mktemp(suffix=".txt"))
>>> file_b = Path(tempfile.mktemp(suffix=".txt"))
>>> _ = file_a.write_text("hello")
>>> _ = file_b.write_text("world")

>>> class BatchLoader(StateChart):
...     loading = State(
...         initial=True,
...         invoke=invoke_group(
...             lambda: file_a.read_text(),
...             lambda: file_b.read_text(),
...         ),
...     )
...     ready = State(final=True)
...     done_invoke_loading = loading.to(ready)
...
...     def on_enter_ready(self, data=None, **kwargs):
...         self.results = data

>>> sm = BatchLoader()
>>> time.sleep(0.2)

>>> "ready" in sm.configuration_values
True
>>> sm.results
['hello', 'world']

>>> file_a.unlink()
>>> file_b.unlink()

```

If any callable raises, the remaining ones are cancelled and an `error.execution`
event is sent. If the owning state is exited before all callables finish, the group
is cancelled.

## Child state machines

Pass a `StateChart` subclass to spawn a child machine:

```python
from statemachine import State, StateChart

class ChildMachine(StateChart):
    start = State(initial=True)
    end = State(final=True)
    go = start.to(end)

    def on_enter_start(self, **kwargs):
        self.send("go")

class ParentMachine(StateChart):
    loading = State(initial=True, invoke=ChildMachine)
    ready = State(final=True)
    done_invoke_loading = loading.to(ready)
```

The child machine is instantiated and run when the parent's `loading` state is entered.
When the child terminates (reaches a final state), a `done.invoke` event is sent to the
parent, triggering the `done_invoke_loading` transition. See
`tests/test_invoke.py::TestInvokeStateChartChild` for a working example.
