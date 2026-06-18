(coming-from-transitions)=

# Coming from pytransitions

This guide helps users of the [*transitions*](https://github.com/pytransitions/transitions)
library migrate to python-statemachine (or evaluate the differences). Code examples are
shown side by side where possible. For a quick overview, jump to the
{ref}`feature matrix <feature-matrix>`.

## At a glance

| Aspect | *transitions* | python-statemachine |
|---|---|---|
| Definition style | Imperative (dicts/lists passed to `Machine`) | Declarative (class-level `State` and `.to()`) |
| State definition | Strings or `State` objects in a list | Class attributes (`State(...)`) |
| Transition definition | `add_transition()` / dicts | `.to()` chaining, `\|` composition |
| Event triggers | Auto-generated methods on the model | `sm.send("event")` or `sm.event()` |
| Callbacks | String names or callables, per-transition | Naming conventions + decorators, {ref}`dependency injection <dependency-injection>` |
| Conditions | `conditions=`, `unless=` | `cond=`, `unless=`, {ref}`expression strings <condition expressions>` |
| Nested states | `HierarchicalMachine` + separator strings | `State.Compound` / `State.Parallel` nested classes |
| Completion events | `on_final` callback only | `done.state` / `done.invoke` {ref}`automatic events <done-state-events>` with `donedata` |
| Invoke | No | {ref}`Background work <invoke>` tied to state lifecycle |
| Async | Separate `AsyncMachine` class | {ref}`Auto-detected <async>` from `async def` callbacks |
| API surface | [12 Machine classes](https://github.com/pytransitions/transitions#-extensions) to combine features | {ref}`Single StateChart class <unified-api>` — all features built in |
| Diagrams | `GraphMachine` (separate base class) | Built-in {ref}`_graph() <diagrams>` on every instance |
| Model binding | `Machine(model=obj)` | {ref}`MachineMixin <machinemixin>` or `model=` parameter |
| Listeners | Machine-level callbacks only | Full {ref}`observer pattern <listeners>` (class-level, constructor, runtime) |
| Error handling | Exceptions propagate | Optional {ref}`catch_errors_as_events <error-execution>` (`error.execution`) |
| Validations | None | {ref}`Structural + callback checks <validations>` at definition and creation time |
| SCXML compliance | [Not a goal](https://github.com/pytransitions/transitions/issues/446#issuecomment-646837282) | {ref}`W3C conformant <processing-model>` with automated test suite |
| Serialization / loading | `markup` dict round-trip (persist as JSON/YAML yourself; no SCXML) | [Secure `io.load()`](../io/index.md) from SCXML, JSON and YAML |
| Processing model | Immediate or queued | Always queued ({ref}`run-to-completion <rtc-model>`) |


## Defining states

In *transitions*, states are defined as strings or dicts passed to the `Machine` constructor.
States can exist without any transitions — the library does not validate structural
consistency:

```python
from transitions import Machine

states = ["draft", "producing", "closed"]
machine = Machine(states=states, initial="draft")
# No transitions defined — "producing" and "closed" are unreachable, but no error is raised
```

In python-statemachine, states are class-level descriptors and **transitions are
required**. The library validates structural integrity at class definition time —
states without transitions are rejected:

```py
>>> from statemachine import State, StateChart
>>> from statemachine.exceptions import InvalidDefinition

>>> try:
...     class BadWorkflow(StateChart):
...         draft = State(initial=True)
...         producing = State()
...         closed = State(final=True)
... except InvalidDefinition as e:
...     print(e)
There are unreachable states. ...Disconnected states: [...]

```

A valid definition requires transitions connecting all states:

```py
>>> class Workflow(StateChart):
...     draft = State(initial=True)
...     producing = State()
...     closed = State(final=True)
...     produce = draft.to(producing)
...     deliver = producing.to(closed)

>>> sm = Workflow()
>>> sm.draft.is_active
True

```

States are first-class objects with properties like `is_active`, `value`, and `id`.
You can set a human-readable name and a persistence value directly on the state.
See {ref}`states` for the full reference.

```py
>>> producing = State("Being produced", value=2)

```

### Flat vs compound definitions

In *transitions*, flat and hierarchical machines are **separate classes**. To use
compound states you must switch from `Machine` to `HierarchicalMachine` and define
the hierarchy through nested dicts — states and their children are described far from
the transitions that connect them:

```python
from transitions.extensions import HierarchicalMachine

states = [
    "idle",
    {
        "name": "active",
        "children": [
            {"name": "working", "on_enter": "start_work"},
            {"name": "paused"},
        ],
        "initial": "working",
    },
    "done",
]

transitions = [
    {"trigger": "start", "source": "idle", "dest": "active"},
    {"trigger": "pause", "source": "active_working", "dest": "active_paused"},
    {"trigger": "resume", "source": "active_paused", "dest": "active_working"},
    {"trigger": "finish", "source": "active", "dest": "done"},
]

machine = HierarchicalMachine(states=states, transitions=transitions, initial="idle")
```

Note how child states are referenced with separator-based names (`active_working`,
`active_paused`) and the structure is split across two separate data structures.

In python-statemachine, `StateChart` handles both flat and compound machines. Compound
states are nested Python classes that act as **namespaces** — children, transitions,
and callbacks are declared together in the class body, mirroring the state hierarchy
directly in code:

```py
>>> from statemachine import State, StateChart

>>> class TaskMachine(StateChart):
...     idle = State(initial=True)
...
...     class active(State.Compound):
...         working = State(initial=True)
...         paused = State()
...         pause = working.to(paused)
...         resume = paused.to(working)
...
...         def on_enter_working(self):
...             self.started = True
...
...     done = State(final=True)
...
...     start = idle.to(active)
...     finish = active.to(done)

>>> sm = TaskMachine()
>>> sm.send("start")
>>> sm.started
True

>>> sm.send("pause")
>>> "paused" in sm.configuration_values
True

>>> sm.send("resume")
>>> sm.send("finish")
>>> sm.done.is_active
True

```

Each compound class is self-contained: its children, internal transitions, and callbacks
live inside the same block. This scales naturally to deeper hierarchies and parallel
regions without switching to a different API.

python-statemachine also supports hierarchical features not available in *transitions*:

- {ref}`History pseudo-states <history-states>` (`HistoryState`) — remember and restore previous child states
- {ref}`Eventless transitions <eventless>` — fire automatically when their guard condition is met

See {ref}`compound-states` and {ref}`parallel-states` for the full reference.


### Creating machines from dicts and documents

If you prefer the dict-based definition style familiar from *transitions*, you can
use {func}`~statemachine.io.create_machine_class_from_definition` to build a
`StateChart` dynamically. It supports states, transitions, conditions, and
callbacks (`on`, `before`, `after`, `enter`, `exit`):

```py
>>> from statemachine.io import create_machine_class_from_definition

>>> TrafficLight = create_machine_class_from_definition(
...     "TrafficLight",
...     states={
...         "green": {
...             "initial": True,
...             "on": {"change": [{"target": "yellow"}]},
...         },
...         "yellow": {
...             "on": {"change": [{"target": "red"}]},
...         },
...         "red": {
...             "on": {"change": [{"target": "green"}]},
...         },
...     },
... )

>>> sm = TrafficLight()
>>> sm.send("change")
>>> sm.yellow.is_active
True
>>> sm.send("change")
>>> sm.red.is_active
True

```

The result is a regular `StateChart` subclass — all features (validations, diagrams,
listeners, async) work exactly the same way. See
{func}`~statemachine.io.create_machine_class_from_definition` for the full API.

#### Loading from SCXML, JSON or YAML documents

*transitions* can serialize a built machine to a Python dict with `MarkupMachine`
(`machine.markup`) and rebuild it via `Machine(markup=...)`. That dict isn't tied to a file
format — you persist it as JSON/YAML yourself — and callbacks and conditions are method-name
strings resolved against the model by import at build time, so it isn't designed to load
untrusted definitions, has no published schema, and doesn't cover SCXML.

python-statemachine provides a first-class, secure loader, {func}`~statemachine.io.load`,
that reads SCXML, JSON and YAML *documents* straight into a `StateChart`:

```python
from statemachine.io import load

Machine = load("traffic_light.scxml")   # or .json / .yaml; format detected from the extension
```

Expressions in the document (guards, datamodel) are evaluated by a restricted allowlist —
never `eval` — so documents from untrusted sources are safe to load; the native JSON/YAML
format has a published JSON Schema (`validate=True`), and SCXML follows the W3C execution
model. See [](../io/index.md) for the full guide.


## Defining transitions

*transitions* uses dicts or `add_transition()`:

```python
transitions = [
    {"trigger": "produce", "source": "draft", "dest": "producing"},
    {"trigger": "deliver", "source": "producing", "dest": "closed"},
    {"trigger": "cancel", "source": ["draft", "producing"], "dest": "cancelled"},
]
machine = Machine(states=states, transitions=transitions, initial="draft")
```

python-statemachine uses `.to()` with `|` for composing multiple origins:

```py
>>> from statemachine import State, StateChart

>>> class Workflow(StateChart):
...     draft = State(initial=True)
...     producing = State()
...     closed = State(final=True)
...     cancelled = State(final=True)
...
...     produce = draft.to(producing)
...     deliver = producing.to(closed)
...     cancel = draft.to(cancelled) | producing.to(cancelled)

>>> sm = Workflow()
>>> sm.send("produce")
>>> sm.producing.is_active
True

```

The `|` operator composes transitions from different sources into a single event.
You can also use `from_()` to express the same thing from the target's perspective.
See {ref}`transitions` for the full reference.

```py
>>> class Workflow2(StateChart):
...     draft = State(initial=True)
...     producing = State()
...     closed = State(final=True)
...     cancelled = State(final=True)
...
...     produce = draft.to(producing)
...     deliver = producing.to(closed)
...     cancel = cancelled.from_(draft, producing)

>>> sm = Workflow2()
>>> sm.send("produce")
>>> sm.send("cancel")
>>> sm.cancelled.is_active
True

```


## Triggering events

In *transitions*, events are called as methods on the model:

```python
machine.produce()   # triggers the "produce" event
machine.deliver()   # triggers the "deliver" event
```

python-statemachine supports both styles:

```py
>>> sm = Workflow()

>>> sm.send("produce")   # send by name (recommended for dynamic dispatch)
>>> sm.producing.is_active
True

>>> sm.deliver()          # call as method (convenient for static usage)
>>> sm.closed.is_active
True

```

`send()` is preferred when the event name comes from external input (e.g., an API
endpoint or message queue). Direct method calls are convenient when you know the
event at coding time. See {ref}`events` for the full reference.


## Callbacks and actions

### *transitions* callback order

In *transitions*, callbacks execute in this order per transition:
`prepare` &rarr; `conditions` &rarr; `before` &rarr; `on_exit_<state>` &rarr; `on_enter_<state>` &rarr; `after`.

Callbacks are specified as strings (method names) or callables:

```python
machine = Machine(
    states=states,
    transitions=[{
        "trigger": "produce",
        "source": "draft",
        "dest": "producing",
        "before": "validate_job",
        "after": "notify_team",
    }],
    initial="draft",
)
```

### python-statemachine callback order

python-statemachine has a similar but more granular order:
`prepare` &rarr; `validators` &rarr; `conditions` &rarr; `before` &rarr; `on_exit` &rarr; `on` &rarr; `on_enter` &rarr; `after`.

The `on` group (between exit and enter) is unique to python-statemachine — it runs the
transition's own action, separate from state entry/exit. See {ref}`actions` for the
full execution order table.

Callbacks are resolved by **naming convention** or by **inline declaration**:

```py
>>> from statemachine import State, StateChart

>>> class Workflow(StateChart):
...     draft = State(initial=True)
...     producing = State()
...     closed = State(final=True)
...
...     produce = draft.to(producing)
...     deliver = producing.to(closed)
...
...     # naming convention: on_enter_<state>
...     def on_enter_producing(self):
...         self.entered = True
...
...     # naming convention: after_<event>
...     def after_produce(self):
...         self.notified = True

>>> sm = Workflow()
>>> sm.send("produce")
>>> sm.entered
True
>>> sm.notified
True

```

Inline callbacks are also supported:

```py
>>> class Workflow2(StateChart):
...     draft = State(initial=True)
...     producing = State()
...     closed = State(final=True)
...
...     produce = draft.to(producing, on="do_produce")
...     deliver = producing.to(closed)
...
...     def do_produce(self):
...         return "producing"

>>> sm = Workflow2()
>>> sm.send("produce")
'producing'

```

### Dependency injection

A key difference: python-statemachine callbacks use **dependency injection** via
`SignatureAdapter`. The engine inspects each callback's signature and passes only
the parameters it accepts. You never need `**kwargs` unless you want to capture extras:

```py
>>> class Workflow(StateChart):
...     draft = State(initial=True)
...     producing = State()
...     closed = State(final=True)
...
...     produce = draft.to(producing)
...     deliver = producing.to(closed)
...
...     def on_produce(self, source, target):
...         return f"{source.id} -> {target.id}"

>>> sm = Workflow()
>>> sm.send("produce")
'draft -> producing'

```

Available parameters include `source`, `target`, `event`, `state`, `error`, and
any custom kwargs passed to `send()`. See {ref}`actions` for the complete list of
available parameters.

In *transitions*, you must accept `**kwargs` or use `EventData`:

```python
def on_enter_producing(self, **kwargs):
    event_data = kwargs.get("event_data")
```


## Conditions and guards

In *transitions*:

```python
machine.add_transition(
    "produce", "draft", "producing",
    conditions=["is_valid", "has_resources"],
    unless=["is_locked"],
)
```

In python-statemachine, use `cond=` and `unless=`:

```py
>>> from statemachine import State, StateChart

>>> class Workflow(StateChart):
...     draft = State(initial=True)
...     producing = State()
...     closed = State(final=True)
...
...     produce = draft.to(producing, cond="is_valid", unless="is_locked")
...     deliver = producing.to(closed)
...
...     is_valid = True
...     is_locked = False

>>> sm = Workflow()
>>> sm.send("produce")
>>> sm.producing.is_active
True

```

python-statemachine also supports **condition expressions** — boolean strings
evaluated at runtime. See {ref}`validators and guards` for the full reference.

```py
>>> class Workflow2(StateChart):
...     draft = State(initial=True)
...     producing = State()
...     closed = State(final=True)
...
...     produce = draft.to(producing, cond="is_valid and not is_locked")
...     deliver = producing.to(closed)
...
...     is_valid = True
...     is_locked = False

>>> sm = Workflow2()
>>> sm.send("produce")
>>> sm.producing.is_active
True

```


## Completion events (`done.state`)

In *transitions*, the `on_final` callback fires when a final state is entered (and
propagates upward when all children of a compound are final). However, it is just a
**callback** — it cannot trigger transitions automatically. You must wire separate
triggers manually.

In python-statemachine, when a compound state's final child is entered, the engine
automatically dispatches a `done.state.<parent_id>` **event**. You define transitions
for it using the `done_state_` naming convention, and the transition fires
automatically — no manual wiring needed:

```py
>>> from statemachine import State, StateChart

>>> class Pipeline(StateChart):
...     class processing(State.Compound):
...         step1 = State(initial=True)
...         step2 = State()
...         completed = State(final=True)
...         advance = step1.to(step2)
...         finish = step2.to(completed)
...     done = State(final=True)
...     done_state_processing = processing.to(done)

>>> sm = Pipeline()
>>> sm.send("advance")
>>> sm.send("finish")
>>> sm.done.is_active
True

```

For parallel states, `done.state` fires only when **all** regions have reached a
final state. Final states can also carry data via `donedata`, which is forwarded
as keyword arguments to the transition handler.

See {ref}`done.state events <done-state-events>` and {ref}`DoneData <donedata>` for
full details.


## Invoke

*transitions* does not have a built-in mechanism for spawning background work tied to
a state's lifecycle.

In python-statemachine, a state can **invoke** external work — API calls, file I/O,
child state machines — when it is entered, and automatically cancel that work when
the state is exited. Handlers run in a background thread (sync engine) or a thread
executor (async engine). When the work completes, a `done.invoke.<state>` event
is automatically dispatched:

```py
>>> import time
>>> from statemachine import State, StateChart

>>> class FetchMachine(StateChart):
...     loading = State(initial=True, invoke=lambda: {"status": "ok"})
...     ready = State(final=True)
...     done_invoke_loading = loading.to(ready)

>>> sm = FetchMachine()
>>> time.sleep(0.1)
>>> sm.ready.is_active
True

```

Invoke supports multiple handlers (`invoke=[a, b]`), grouped invocations
(`invoke_group`), child state machines, and the full callback naming conventions
(`on_invoke_<state>`, `@state.invoke`).

See {ref}`invoke` for full documentation.


## Async support

*transitions* requires a separate class:

```python
from transitions.extensions import AsyncMachine

class AsyncModel:
    async def on_enter_producing(self):
        await some_async_operation()

machine = AsyncMachine(model=AsyncModel(), states=states, initial="draft")
await machine.produce()
```

python-statemachine auto-detects async callbacks — no special class needed:

```py
>>> import asyncio

>>> from statemachine import State, StateChart

>>> class AsyncWorkflow(StateChart):
...     draft = State(initial=True)
...     producing = State(final=True)
...
...     produce = draft.to(producing)
...
...     async def on_enter_producing(self):
...         return "async entered"

>>> async def main():
...     sm = AsyncWorkflow()
...     await sm.send("produce")
...     return sm.producing.is_active

>>> asyncio.run(main())
True

```

If any callback is `async def`, the engine automatically switches to the async
processing loop. Sync and async callbacks can be mixed freely.
See {ref}`async` for the full reference.


## Diagrams

In *transitions*, diagram support requires replacing `Machine` with `GraphMachine`
— a separate base class. If you also need nested states, you must use
`HierarchicalGraphMachine`; add async and it becomes
`HierarchicalAsyncGraphMachine`. This is part of the
{ref}`class composition problem <unified-api>` discussed below.

```python
from transitions.extensions import GraphMachine

machine = GraphMachine(model=model, states=states, transitions=transitions, initial="draft")
machine.get_graph().draw("diagram.png", prog="dot")
```

In python-statemachine, diagram generation is available on **every** state machine
with no class changes. Every instance has a `_graph()` method built in, and
`_repr_svg_()` renders directly in Jupyter notebooks:

```py
>>> from statemachine import State, StateChart

>>> class Workflow(StateChart):
...     draft = State(initial=True)
...     producing = State()
...     closed = State(final=True)
...     produce = draft.to(producing)
...     deliver = producing.to(closed)

>>> sm = Workflow()
>>> graph = sm._graph()
>>> type(graph).__name__
'Dot'

```

For more control, use `DotGraphMachine` directly:

```python
from statemachine.contrib.diagram import DotGraphMachine

graph = DotGraphMachine(Workflow)
graph().write_png("diagram.png")
```

Diagrams automatically render compound and parallel state hierarchies.
See {ref}`diagrams` for the full reference.


(unified-api)=

## Unified API vs class composition

One of the most significant architectural differences between the two libraries
is how features are composed.

In *transitions*, each feature lives in a separate `Machine` subclass. Combining
features requires using pre-built combined classes — the number of variants grows
combinatorially:

| Class | Nested | Diagrams | Locked | Async |
|---|:---:|:---:|:---:|:---:|
| `Machine` | | | | |
| `HierarchicalMachine` | x | | | |
| `GraphMachine` | | x | | |
| `LockedMachine` | | | x | |
| `AsyncMachine` | | | | x |
| `HierarchicalGraphMachine` | x | x | | |
| `LockedGraphMachine` | | x | x | |
| `LockedHierarchicalMachine` | x | | x | |
| `LockedHierarchicalGraphMachine` | x | x | x | |
| `AsyncGraphMachine` | | x | | x |
| `HierarchicalAsyncMachine` | x | | | x |
| `HierarchicalAsyncGraphMachine` | x | x | | x |

That is **12 classes** to cover all combinations — and switching from a flat
machine to a hierarchical one requires changing the base class across your
codebase.

In python-statemachine, `StateChart` is the single base class. All features are
always available:

- **Nested states** — use `State.Compound` / `State.Parallel` in the class body
- **Async** — auto-detected from `async def` callbacks
- **Diagrams** — built-in `_graph()` on every instance
- **Thread safety** — handled by the engine's run-to-completion processing loop

```py
>>> import asyncio
>>> from statemachine import State, StateChart

>>> class FullFeatured(StateChart):
...     """Nested + async + diagrams — same single base class."""
...     class phase(State.Compound):
...         step1 = State(initial=True)
...         step2 = State(final=True)
...         advance = step1.to(step2)
...     done = State(final=True)
...     done_state_phase = phase.to(done)
...
...     async def on_enter_done(self):
...         self.result = "async action completed"

>>> async def main():
...     sm = FullFeatured()
...     graph = sm._graph()  # diagrams work
...     await sm.send("advance")  # async works
...     return sm.result

>>> asyncio.run(main())
'async action completed'

```

No class swapping, no feature matrices to consult — just `StateChart`.


## Model integration

*transitions* binds directly to a model object:

```python
class MyModel:
    pass

model = MyModel()
machine = Machine(model=model, states=states, transitions=transitions, initial="draft")
model.produce()  # events are added to the model
```

python-statemachine offers two approaches. See {ref}`domain models` for the full
reference.

**1. Pass a model to the state machine:**

```py
>>> from statemachine import State, StateChart

>>> class MyModel:
...     pass

>>> class Workflow(StateChart):
...     draft = State(initial=True)
...     producing = State(final=True)
...     produce = draft.to(producing)

>>> model = MyModel()
>>> sm = Workflow(model=model)
>>> sm.model is model
True

```

**2. Use `MachineMixin` for ORM integration:**

```py
>>> from statemachine.mixins import MachineMixin

>>> class WorkflowModel(MachineMixin):
...     state_machine_name = "__main__.Workflow"
...     state_machine_attr = "sm"
...     bind_events_as_methods = True
...
...     state = 0  # persisted field

```

`MachineMixin` is particularly useful with Django models, where the state field
is a database column. See {ref}`integrations <machinemixin>` for details.


## Listeners

In *transitions*, cross-cutting concerns like logging or auditing are handled through
machine-level callbacks (`prepare_event`, `finalize_event`, `on_exception`). These are
callables passed to the `Machine` constructor — not separate objects. All callbacks
must live on the model or be passed as functions:

```python
machine = Machine(
    model=model,
    states=states,
    transitions=transitions,
    initial="draft",
    prepare_event="log_event",
    finalize_event="cleanup",
)
```

python-statemachine has a full **listener/observer pattern**. A listener is any object
with methods matching the callback naming conventions — no base class required. Listeners
are first-class: they receive the same callbacks as the state machine itself, with full
{ref}`dependency injection <dependency-injection>`:

```py
>>> from statemachine import State, StateChart

>>> class AuditListener:
...     def __init__(self):
...         self.log = []
...     def after_transition(self, event, source, target):
...         self.log.append(f"{event}: {source.id} -> {target.id}")

>>> class OrderMachine(StateChart):
...     listeners = [AuditListener]
...     draft = State(initial=True)
...     confirmed = State(final=True)
...     confirm = draft.to(confirmed)

>>> sm = OrderMachine()
>>> sm.send("confirm")
>>> sm.active_listeners[0].log
['confirm: draft -> confirmed']

```

Listeners can be declared at the class level (`listeners = [...]`), passed at
construction time (`OrderMachine(listeners=[...])`), or attached at runtime
(`sm.add_listener(...)`). Multiple independent listeners compose naturally — each
receives only the parameters it declares.

Class-level listeners support inheritance (child listeners append after parent),
a `setup()` protocol for receiving runtime dependencies (DB sessions, Redis
clients), and `functools.partial` for configuration.

See {ref}`listeners` for the full reference.


## Error handling

*transitions* lets exceptions propagate normally:

```python
try:
    machine.produce()
except SomeError:
    # handle error
    pass
```

python-statemachine supports both styles. With `StateMachine` (the 2.x base class),
exceptions propagate as in *transitions*. With `StateChart`, you can opt into
structured error handling:

```py
>>> from statemachine import State, StateChart

>>> class RobustWorkflow(StateChart):
...     draft = State(initial=True)
...     error_state = State(final=True)
...
...     go = draft.to(draft, on="bad_action")
...     error_execution = draft.to(error_state)
...
...     def bad_action(self):
...         raise RuntimeError("something went wrong")

>>> sm = RobustWorkflow()
>>> sm.send("go")
>>> sm.error_state.is_active
True

```

When `catch_errors_as_events=True` (default in `StateChart`), runtime exceptions
are caught and dispatched as `error.execution` internal events. You can define
transitions that handle these errors, keeping the state machine in a consistent
state. The error object is available as `error` in callback kwargs.

See {ref}`error handling <error-execution>` for full details.


## Validations

*transitions* does not validate the consistency of your state machine definition.
You can define unreachable states, trap states (non-final states with no outgoing
transitions), or reference nonexistent callback names — and the library will not
warn you. Errors only surface at runtime, when an event fails to trigger or a
callback is not found.

python-statemachine validates the statechart structure at **two stages**:

1. **Class definition time** — structural checks run as soon as the class body is
   evaluated. If any check fails, the class itself is not created:

```py
>>> from statemachine import State, StateChart
>>> from statemachine.exceptions import InvalidDefinition

>>> try:
...     class Bad(StateChart):
...         red = State(initial=True)
...         green = State()
...         hazard = State()
...         cycle = red.to(green) | green.to(red)
...         blink = hazard.to.itself()
... except InvalidDefinition as e:
...     print(e)
There are unreachable states. The statemachine graph should have a single component. Disconnected states: ['hazard']

```

2. **Instance creation time** — callback resolution, boolean expression parsing,
   and other runtime checks:

```py
>>> class MyChart(StateChart):
...     a = State(initial=True)
...     b = State(final=True)
...     go = a.to(b, on="nonexistent_method")

>>> try:
...     MyChart()
... except InvalidDefinition as e:
...     assert "Did not found name 'nonexistent_method'" in str(e)

```

Built-in validations include: exactly one initial state, no transitions from final
states, unreachable states, trap states, final state reachability, internal
transition targets, callback resolution, and boolean expression parsing.
See {ref}`validations` for the full list.


(feature-matrix)=

## Feature matrix

| Feature | *transitions* | python-statemachine |
|---|:---:|:---:|
| Flat state machines | Yes | Yes |
| {ref}`Compound (nested) states <compound-states>` | Yes | Yes |
| {ref}`Parallel states <parallel-states>` | Yes | Yes |
| {ref}`History pseudo-states <history-states>` | No | **Yes** |
| {ref}`Eventless transitions <eventless>` | No | **Yes** |
| {ref}`Final states <final-state>` | Yes | Yes |
| {ref}`Condition expressions <condition expressions>` | No | **Yes** |
| {ref}`In() state checks <condition expressions>` | No | **Yes** |
| {ref}`Dependency injection <dependency-injection>` | No | **Yes** |
| {ref}`Auto async detection <async>` | No | **Yes** |
| {ref}`error.execution handling <error-execution>` | No | **Yes** |
| {ref}`done.state / done.invoke events <done-state-events>` | Callback only | **Yes** |
| {ref}`Delayed events <delayed-events>` | No | **Yes** |
| {ref}`Internal events (raise_()) <sending-events>` | No | **Yes** |
| {ref}`Invoke (background work) <invoke>` | No | **Yes** |
| {ref}`Listener/observer pattern <listeners>` | No | **Yes** |
| {ref}`Definition-time validations <validations>` | No | **Yes** |
| {ref}`SCXML conformance <processing-model>` | No | **Yes** |
| [Load from SCXML/JSON/YAML documents](../io/index.md) | No | **Yes** |
| Serialize a built machine to a portable definition | Yes (`markup`) | Partial (load only) |
| {ref}`Diagrams <diagrams>` | Yes | Yes |
| {ref}`Django integration <machinemixin>` | Community | Built-in |
| {ref}`Model binding <models>` | Yes | Yes |
| {ref}`Wildcard transitions (*) <events>` | Yes | Yes |
| {ref}`Reflexive transitions <self-transition>` | Yes | Yes |
| Ordered transitions | Yes | Via explicit wiring |
| Tags on states | Yes | Via subclassing |
| {ref}`Machine nesting (children) <invoke>` | Yes | Yes (invoke) |
| {ref}`Timeout transitions <timeout>` | Yes | Yes |
