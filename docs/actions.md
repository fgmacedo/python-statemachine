(actions)=

# Actions

```{seealso}
New to statecharts? See [](concepts.md) for an overview of how states,
transitions, events, and actions fit together.
```

An **action** is a side-effect that runs during a state change — sending
notifications, updating a database, logging, or returning a value. Actions are
the main reason statecharts exist: they ensure the right code runs at the right
time, depending on the sequence of events and the current state.


## Execution order

A single {ref}`microstep <macrostep-microstep>` executes callbacks in a fixed
sequence of **groups**. Each group runs to completion before the next one starts:

```{list-table}
:header-rows: 1

*   - Group
    - Callbacks
    - `state` is
    - Description
*   - Prepare
    - `prepare_event()`
    - `source`
    - Enrich event kwargs before anything else runs. See {ref}`preparing-events`.
*   - Validators
    - `validators`
    - `source`
    - Raise an exception to block the transition.
*   - Conditions
    - `cond`, `unless`
    - `source`
    - Return a boolean to allow or prevent the transition.
*   - Before
    - `before_transition()`, `before_<event>()`
    - `source`
    - Runs before any state changes.
*   - Exit
    - `on_exit_state()`, `on_exit_<state>()`
    - exiting state
    - Runs once per state being exited, from child to ancestor.
*   - On
    - `on_transition()`, `on_<event>()`
    - `source`
    - Transition content — the main action.
*   - Enter
    - `on_enter_state()`, `on_enter_<state>()`
    - entering state
    - Runs once per state being entered, from ancestor to child.
*   - Invoke
    - `on_invoke_state()`, `on_invoke_<state>()`
    - `target`
    - Spawns background work. See {ref}`invoke`.
*   - After
    - `after_transition()`, `after_<event>()`
    - `target`
    - Runs after all state changes are complete.
```

The `state` column shows what the `state` parameter resolves to when
{ref}`injected <dependency-injection>` into that callback. The `source` and
`target` parameters are always available regardless of group.

```{tip}
`after` callbacks run even when an earlier group raises and
`error_on_execution` is enabled — making them a natural **finalize** hook.
See {ref}`error-handling-cleanup-finalize` for the full pattern.
```

```{seealso}
See {ref}`validators and guards` for the `validators`, `cond`, and `unless`
groups. The rest of this page focuses on actions.
```


### Priority within a group

Each group can contain multiple callbacks. Within the same group, callbacks
execute in **priority order**:

1. **Generic** — built-in callbacks like `on_enter_state()` or `before_transition()`.
2. **Inline** — callbacks passed as constructor parameters (e.g., `on="do_work"`).
3. **Decorator** — callbacks added via decorators (e.g., `@state.enter`).
4. **Naming convention** — callbacks discovered by name (e.g., `on_enter_idle()`).

```{seealso}
See the example {ref}`sphx_glr_auto_examples_all_actions_machine.py` for a
complete demonstration of callback resolution order.
```


### Exit and enter in compound states

In a flat state machine, exit and enter each run exactly once — for the
single source and the single target. With {ref}`compound <compound-states>`
and {ref}`parallel <parallel-states>` states, a transition may cross
multiple levels of the hierarchy, and the engine exits and enters **each
level individually**, following the
[SCXML](https://www.w3.org/TR/scxml/#AlgorithmforSCXMLInterpretation)
specification:

- **Exit** runs from the **innermost** (deepest child) state up to the
  ancestor being left — children exit before their parents.
- **Enter** runs from the **outermost** (highest ancestor) state down to
  the target leaf — parents enter before their children.

```py
>>> from statemachine import State, StateChart

>>> class HierarchicalExample(StateChart):
...     class parent_a(State.Compound):
...         child_a = State(initial=True)
...     class parent_b(State.Compound):
...         child_b = State(initial=True, final=True)
...     cross = parent_a.to(parent_b)
...
...     def on_exit_child_a(self):
...         print("  exit  child_a")
...     def on_exit_parent_a(self):
...         print("  exit  parent_a")
...     def on_enter_parent_b(self):
...         print("  enter parent_b")
...     def on_enter_child_b(self):
...         print("  enter child_b")

>>> sm = HierarchicalExample()
>>> sm.send("cross")
  exit  child_a
  exit  parent_a
  enter parent_b
  enter child_b

```

This means that **exit and enter callbacks fire multiple times per
microstep** — once for each state in the exit/entry set. Use state-specific
callbacks (`on_exit_<state>`, `on_enter_<state>`) to target individual
levels of the hierarchy.

```{note}
The generic `on_exit_state()` and `on_enter_state()` callbacks also fire
once per state in the set, but the `state` parameter is bound to the
transition's `source` or `target` — not the individual state being
exited/entered. Use `event_data` if you need the full context, or prefer
state-specific callbacks for clarity.
```

```{seealso}
See {ref}`macrostep-microstep` for how microsteps compose into macrosteps,
and {ref}`compound-states` for how state hierarchies work.
```


(dependency-injection)=
(dynamic-dispatch)=
(dynamic dispatch)=

## Dependency injection

All callbacks (actions, conditions, validators) support automatic dependency
injection. The library inspects your method signature and passes only the
parameters you declare — you never need to accept arguments you don't use.

```py
>>> class FlexibleSC(StateChart):
...     idle = State(initial=True)
...     done = State(final=True)
...
...     go = idle.to(done)
...
...     def on_go(self):
...         """No params needed? That's fine."""
...         return "minimal"
...
...     def after_go(self, event, source, target):
...         """Need context? Just declare what you want."""
...         print(f"{event}: {source.id} → {target.id}")

>>> sm = FlexibleSC()
>>> sm.send("go")
go: idle → done
'minimal'

```

### Available parameters

These parameters are available for injection into any callback:

| Parameter | Type | Description |
|---|---|---|
| `event_data` | {class}`~statemachine.event_data.EventData` | The full event data object for this microstep. |
| `event` | {class}`~statemachine.event.Event` | The event that triggered the transition. |
| `source` | {class}`~statemachine.state.State` | The state the machine was in when the event started. |
| `target` | {class}`~statemachine.state.State` | The destination state of the transition. |
| `state` | {class}`~statemachine.state.State` | The *current* state — equals `source` for before/exit/on, `target` for enter/after. |
| `error` | `Exception` | The exception object. Only available in callbacks triggered by `error.execution` events. See {ref}`error-execution`. |
| `model` | {class}`~statemachine.model.Model` | The underlying model instance (see {ref}`models`). |
| `machine` | {class}`~statemachine.statemachine.StateChart` | The state machine instance itself. |
| `transition` | {class}`~statemachine.transition.Transition` | The transition being executed. |

The following parameters are available **only in `on` callbacks** (transition
content):

| Parameter | Type | Description |
|---|---|---|
| `previous_configuration` | `OrderedSet[`{class}`~statemachine.state.State``]` | States that were active before the microstep. |
| `new_configuration` | `OrderedSet[`{class}`~statemachine.state.State``]` | States that will be active after the microstep. |

#### Configuration during `on` callbacks

By the time the `on` group runs, exit callbacks have already fired and the
exiting states may have been removed from `sm.configuration`, but the entering
states have not been added yet. This means that reading `sm.configuration`
inside an `on` callback returns a **transitional** snapshot — neither the old
nor the new configuration.

Use `previous_configuration` and `new_configuration` instead to reliably
inspect which states were active before and which will be active after:

```py
>>> from statemachine import State, StateChart

>>> class InspectConfig(StateChart):
...     a = State(initial=True)
...     b = State(final=True)
...
...     go = a.to(b)
...
...     def on_go(self, previous_configuration, new_configuration):
...         current = {s.id for s in self.configuration}
...         prev = {s.id for s in previous_configuration}
...         new = {s.id for s in new_configuration}
...         print(f"previous:      {sorted(prev)}")
...         print(f"configuration: {sorted(current)}")
...         print(f"new:           {sorted(new)}")

>>> sm = InspectConfig()
>>> sm.send("go")
previous:      ['a']
configuration: []
new:           ['b']

```

Notice that `sm.configuration` is **empty** during the `on` callback — state
`a` has already exited, but state `b` has not entered yet.

```{tip}
If you need the old 2.x behavior where `sm.configuration` updates atomically
(all exits and entries applied at once after the `on` group), set
`atomic_configuration_update = True` on your class. See the
[behaviour reference](behaviour.md) for details.
```

In addition, any positional or keyword arguments you pass when triggering the
event are forwarded to all callbacks:

```py
>>> class Greeter(StateChart):
...     idle = State(initial=True)
...
...     greet = idle.to.itself()
...
...     def on_greet(self, name, greeting="Hello"):
...         return f"{greeting}, {name}!"

>>> sm = Greeter()
>>> sm.send("greet", "Alice")
'Hello, Alice!'

>>> sm.send("greet", "Bob", greeting="Hi")
'Hi, Bob!'

```

```{seealso}
All actions and {ref}`conditions <validators and guards>` support the same
dependency injection mechanism. See {ref}`validators and guards` for how it
applies to guards.
```


## Binding actions

There are three ways to attach an action to a state or transition: **naming
conventions**, **inline parameters**, and **decorators**. All three can be
combined — the priority rules above determine execution order.


(state-actions)=

### State actions

States support `enter` and `exit` callbacks.

**Naming convention** — define a method matching `on_enter_<state_id>()` or
`on_exit_<state_id>()`:

```py
>>> from statemachine import StateChart, State

>>> class LoginFlow(StateChart):
...     idle = State(initial=True)
...     logged_in = State(final=True)
...
...     login = idle.to(logged_in)
...
...     def on_enter_logged_in(self):
...         print("session started")

>>> sm = LoginFlow()
>>> sm.send("login")
session started

```

**Inline parameter** — pass callback names to the `State` constructor:

```py
>>> class LoginFlow(StateChart):
...     idle = State(initial=True)
...     logged_in = State(final=True, enter="start_session")
...
...     login = idle.to(logged_in)
...
...     def start_session(self):
...         print("session started")

>>> sm = LoginFlow()
>>> sm.send("login")
session started

```

**Decorator** — use `@state.enter` or `@state.exit`:

```py
>>> class LoginFlow(StateChart):
...     idle = State(initial=True)
...     logged_in = State(final=True)
...
...     login = idle.to(logged_in)
...
...     @logged_in.enter
...     def start_session(self):
...         print("session started")

>>> sm = LoginFlow()
>>> sm.send("login")
session started

```

States also support `invoke` callbacks — background work that is spawned when
the state is entered and automatically cancelled when the state is exited.
Invoke supports the same three binding patterns (naming convention, inline,
decorator) and has its own completion and cancellation lifecycle.

```{seealso}
See {ref}`invoke` for the full invoke reference: execution model, binding
patterns, `done.invoke` transitions, cancellation, error handling, grouped
invokes, the `IInvoke` protocol, and child state machines.
```


(transition-actions)=

### Transition actions

Transitions support `before`, `on`, and `after` callbacks.

**Naming convention** — define a method matching `before_<event>()`,
`on_<event>()`, or `after_<event>()`. The callback is called for every
transition triggered by that event:

```py
>>> from statemachine import StateChart, State

>>> class Turnstile(StateChart):
...     locked = State(initial=True)
...     unlocked = State()
...
...     coin = locked.to(unlocked)
...     push = unlocked.to(locked)
...
...     def on_coin(self):
...         return "accepted"
...
...     def after_push(self):
...         print("gate closed")

>>> sm = Turnstile()
>>> sm.send("coin")
'accepted'

>>> sm.send("push")
gate closed

```

**Inline parameter** — pass callback names to the transition constructor:

```py
>>> class Turnstile(StateChart):
...     locked = State(initial=True)
...     unlocked = State()
...
...     coin = locked.to(unlocked, on="accept_coin")
...     push = unlocked.to(locked, after="close_gate")
...
...     def accept_coin(self):
...         return "accepted"
...
...     def close_gate(self):
...         print("gate closed")

>>> sm = Turnstile()
>>> sm.send("coin")
'accepted'

>>> sm.send("push")
gate closed

```

**Decorator** — use `@event.before`, `@event.on`, or `@event.after`:

```py
>>> class Turnstile(StateChart):
...     locked = State(initial=True)
...     unlocked = State()
...
...     coin = locked.to(unlocked)
...     push = unlocked.to(locked)
...
...     @coin.on
...     def accept_coin(self):
...         return "accepted"
...
...     @push.after
...     def close_gate(self):
...         print("gate closed")

>>> sm = Turnstile()
>>> sm.send("coin")
'accepted'

>>> sm.send("push")
gate closed

```

#### Declaring an event with an inline action

You can declare an event and its `on` action in a single expression by using the
transition as a decorator:

```py
>>> class Turnstile(StateChart):
...     locked = State(initial=True)
...     unlocked = State()
...
...     push = unlocked.to(locked)
...
...     @locked.to(unlocked)
...     def coin(self):
...         return "accepted"

>>> sm = Turnstile()
>>> sm.send("coin")
'accepted'

```

The resulting `coin` attribute is an {ref}`Event <events>`, not a plain method —
it only executes when the machine is in a state where a matching transition
exists.


## Generic callbacks

Generic callbacks run on **every** transition, regardless of which event or
state is involved. They follow the same group ordering and are useful for
cross-cutting concerns like logging or auditing:

```py
>>> class Audited(StateChart):
...     idle = State(initial=True)
...     active = State(final=True)
...
...     start = idle.to(active)
...
...     def before_transition(self, event, source):
...         print(f"about to transition from {source.id} on {event}")
...
...     def on_enter_state(self, target, event):
...         print(f"entered {target.id} on {event}")
...
...     def after_transition(self, event, source, target):
...         print(f"completed {source.id} → {target.id} on {event}")

>>> sm = Audited()
entered idle on __initial__

>>> sm.send("start")
about to transition from idle on start
entered active on start
completed idle → active on start

```

The full list of generic callbacks:

| Callback | Group | Description |
|---|---|---|
| `before_transition()` | Before | Runs before any state change. |
| `on_exit_state()` | Exit | Runs when leaving any state. |
| `on_transition()` | On | Runs during any transition. |
| `on_enter_state()` | Enter | Runs when entering any state. |
| `on_invoke_state()` | Invoke | Runs when spawning invoke handlers for any state. See {ref}`invoke`. |
| `after_transition()` | After | Runs after all state changes. |

```{note}
`prepare_event()` is also a generic callback, but it serves a special purpose —
see {ref}`preparing-events` below.
```

```{tip}
Generic callbacks are the building blocks for {ref}`listeners <listeners>` — an
external object that implements the same callback signatures can observe every
transition without modifying the state machine class.
```


(preparing-events)=

## Preparing events

The `prepare_event` callback runs **before validators and conditions** and has a
unique capability: its return value (a `dict`) is merged into the keyword
arguments available to all subsequent callbacks in the same microstep.

This is useful for enriching events with computed context — for example, looking
up a user record from an ID before the transition runs:

```py
>>> class OrderFlow(StateChart):
...     pending = State(initial=True)
...     confirmed = State(final=True)
...
...     confirm = pending.to(confirmed)
...
...     def prepare_event(self, order_id=None):
...         if order_id is not None:
...             return {"order_total": order_id * 10}
...         return {}
...
...     def on_confirm(self, order_total=0):
...         return f"confirmed ${order_total}"

>>> sm = OrderFlow()
>>> sm.send("confirm", order_id=5)
'confirmed $50'

```


## Return values

The return values from `before` and `on` callbacks are collected into a list
and returned to the caller. Other groups (`exit`, `enter`, `after`) do not
contribute to the return value.

```py
>>> class ReturnExample(StateChart):
...     a = State(initial=True)
...     b = State(final=True)
...
...     go = a.to(b)
...
...     def before_go(self):
...         return "before"
...
...     def on_go(self):
...         return "on"
...
...     def on_enter_b(self):
...         return "enter (ignored)"
...
...     def after_go(self):
...         return "after (ignored)"

>>> sm = ReturnExample()
>>> sm.send("go")
['before', 'on']

```

When only one callback returns a value, the result is unwrapped (not a list):

```py
>>> class SingleReturn(StateChart):
...     a = State(initial=True)
...     b = State(final=True)
...
...     go = a.to(b, on="do_it")
...
...     def do_it(self):
...         return 42

>>> sm = SingleReturn()
>>> sm.send("go")
42

```

When no callback returns a value, the result is `None`:

```py
>>> class NoReturn(StateChart):
...     a = State(initial=True)
...     b = State(final=True)
...
...     go = a.to(b)

>>> sm = NoReturn()
>>> sm.send("go") is None
True

```

```{note}
If a callback is defined but returns `None` explicitly, it is included in the
result list. Only callbacks that are not defined at all are excluded.
```
