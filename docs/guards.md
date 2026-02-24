(validators-and-guards)=
(validators and guards)=

# Conditions

```{seealso}
New to statecharts? See [](concepts.md) for an overview of how states,
transitions, events, and actions fit together.
```

Conditions and validators are checked **before** a transition starts — they
decide whether the transition is allowed to proceed.

The difference is in how they communicate rejection:

| Mechanism | Rejects by | Use when |
|---|---|---|
| {ref}`Conditions <conditions>` (`cond` / `unless`) | Returning a falsy value | You want the engine to silently skip the transition and try the next one. |
| {ref}`Validators <validators>` | Raising an exception | You want the caller to know *why* the transition was rejected. |

Both run in the **transition-selection** phase, before any state changes
occur. See the {ref}`execution order <actions>` table for where they fit in
the callback sequence.


(guards)=
(conditions)=

## Conditions

A **condition** (also known as a _guard_) is a boolean predicate attached to a
transition. When an event arrives, the engine checks each candidate transition
in {ref}`declaration order <transition-priority>` — the first transition whose
conditions are all satisfied is selected. If none match, the event is either
ignored or raises an exception (see `allow_event_without_transition` in the
{ref}`behaviour reference <behaviour>`).

```{important}
A condition must not have side effects. Side effects belong in
{ref}`actions`.
```

There are two guard clause variants:

`cond`
: A list of condition expressions. The transition is allowed only if **all**
  evaluate to `True`.
  - Single: `cond="is_valid"`
  - Multiple: `cond=["is_valid", "has_stock"]`

`unless`
: Same as `cond`, but the transition is allowed only if **all** evaluate to
  `False`.
  - Single: `unless="is_blocked"`
  - Multiple: `unless=["is_blocked", "is_expired"]`

```py
>>> from statemachine import State, StateChart

>>> class ApprovalFlow(StateChart):
...     pending = State(initial=True)
...     approved = State(final=True)
...     rejected = State(final=True)
...
...     approve = pending.to(approved, cond="is_manager")
...     reject = pending.to(rejected)
...
...     is_manager = False

>>> sm = ApprovalFlow()
>>> sm.send("approve")  # cond is False — no transition
>>> "pending" in sm.configuration_values
True

>>> sm.is_manager = True
>>> sm.send("approve")
>>> "approved" in sm.configuration_values
True

```

### Multiple conditional transitions

When multiple transitions share the same event, guards let the engine pick the
right one at runtime. Transitions are checked in **declaration order** (the
order of `.to()` calls), not the order they appear in the `|` composition:

```py
>>> class PriorityRouter(StateChart):
...     inbox = State(initial=True)
...     urgent = State(final=True)
...     normal = State(final=True)
...     low = State(final=True)
...
...     # Declaration order = evaluation order
...     route = (
...         inbox.to(urgent, cond="is_urgent")
...         | inbox.to(normal, cond="is_normal")
...         | inbox.to(low)  # fallback — no condition
...     )
...
...     def is_urgent(self, priority=0, **kwargs):
...         return priority >= 9
...
...     def is_normal(self, priority=0, **kwargs):
...         return priority >= 5

>>> sm = PriorityRouter()
>>> sm.send("route", priority=2)
>>> "low" in sm.configuration_values  # fallback
True

>>> sm = PriorityRouter()
>>> sm.send("route", priority=7)
>>> "normal" in sm.configuration_values
True

>>> sm = PriorityRouter()
>>> sm.send("route", priority=10)
>>> "urgent" in sm.configuration_values  # checked first
True

```

Condition methods receive the same keyword arguments passed to `send()` via
{ref}`dependency injection <dependency-injection>` — declare only the
parameters you need.

```{seealso}
See {ref}`sphx_glr_auto_examples_air_conditioner_machine.py` for another
example combining multiple transitions on the same event.
```


(condition expressions)=

### Condition expressions

Conditions support a mini-language for boolean expressions, allowing guards
to be defined as strings that reference attributes on the state machine, its
model, or registered {ref}`listeners <listeners>`.

The mini-language is based on Python's built-in
[`ast`](https://docs.python.org/3/library/ast.html) parser, so the syntax
is familiar:

```py
>>> class AccessControl(StateChart):
...     locked = State(initial=True)
...     unlocked = State(final=True)
...
...     unlock = locked.to(unlocked, cond="has_key and not is_locked_out")
...
...     has_key = True
...     is_locked_out = False

>>> sm = AccessControl()
>>> sm.send("unlock")
>>> "unlocked" in sm.configuration_values
True

```

```{tip}
All condition expressions are validated when the `StateChart` class is
created. Invalid attribute names raise `InvalidDefinition` immediately,
helping you catch typos early.
```

#### Syntax elements

**Names** refer to attributes on the state machine instance, its model, or
listeners. They can point to properties, attributes, or methods:

- `is_active` — evaluated as `self.is_active` (property/attribute)
- `check_stock` — if it's a method, it's called with
  {ref}`dependency injection <dependency-injection>`

**Boolean operators** (highest to lowest precedence):

1. `not` / `!` — Logical negation
2. `and` / `^` — Logical conjunction
3. `or` / `v` — Logical disjunction

**Comparison operators:**

`>`, `>=`, `==`, `!=`, `<`, `<=`

**Parentheses** control evaluation order:

```python
cond="(is_admin or is_moderator) and not is_banned"
```

#### Expression examples

- `is_logged_in and has_permission`
- `not is_active or is_admin`
- `!(is_guest ^ has_access)`
- `(is_admin or is_moderator) and !is_banned`
- `count > 0 and count <= 10`

```{seealso}
See {ref}`sphx_glr_auto_examples_lor_machine.py` for a complete example
using boolean algebra in conditions.
```


(checking enabled events)=

### Checking enabled events

The {ref}`allowed_events <querying-events>` property returns events
reachable from the current state based on topology alone — it does
**not** evaluate guards. To check which events currently have their
conditions satisfied, use `enabled_events()`:

```py
>>> class TaskMachine(StateChart):
...     idle = State(initial=True)
...     running = State(final=True)
...
...     start = idle.to(running, cond="has_enough_resources")
...
...     def has_enough_resources(self, cpu=0, **kwargs):
...         return cpu >= 4

>>> sm = TaskMachine()

>>> [e.id for e in sm.allowed_events]
['start']

>>> sm.enabled_events()
[]

>>> [e.id for e in sm.enabled_events(cpu=8)]
['start']

```

`enabled_events()` accepts `*args` / `**kwargs` that are forwarded to the
condition callbacks, just like when triggering an event. This makes it
useful for UI scenarios where you want to show or hide buttons based on
whether an event's conditions are currently satisfied.

```{note}
An event is considered **enabled** if at least one of its transitions from
the current state has all conditions satisfied. If a condition raises an
exception, the event is treated as enabled (permissive behavior).
```


(validators)=

## Validators

Validators are imperative guards that **raise an exception** to reject a
transition. While conditions silently skip a transition and let the engine
try the next candidate, validators communicate the rejection reason directly
to the caller.

- Single: `validators="check_stock"`
- Multiple: `validators=["check_stock", "check_credit"]`

```py
>>> class OrderMachine(StateChart):
...     pending = State(initial=True)
...     confirmed = State(final=True)
...
...     confirm = pending.to(confirmed, validators="check_stock")
...
...     def check_stock(self, quantity=0, **kwargs):
...         if quantity <= 0:
...             raise ValueError("Quantity must be positive")

>>> sm = OrderMachine()

>>> sm.send("confirm", quantity=0)
Traceback (most recent call last):
    ...
ValueError: Quantity must be positive

>>> "pending" in sm.configuration_values  # state unchanged
True

>>> sm.send("confirm", quantity=5)  # retry with valid data
>>> "confirmed" in sm.configuration_values
True

```


### Validators always propagate

Validator exceptions **always propagate** to the caller, regardless of the
`catch_errors_as_events` flag. This is intentional: validators operate in the
**transition-selection** phase, not the execution phase. A validator that
rejects is semantically equivalent to a condition that returns `False` —
the transition simply should not happen. The difference is that the
validator communicates the reason via an exception.

This means that even when `catch_errors_as_events = True` (the default for
`StateChart`):

- Validator exceptions are **not** converted to `error.execution` events.
- Validator exceptions do **not** trigger `error.execution` transitions.
- The caller receives the exception directly and can handle it with
  `try`/`except`.

```py
>>> class GuardedWithErrorHandler(StateChart):
...     idle = State(initial=True)
...     active = State()
...     error_state = State(final=True)
...
...     start = idle.to(active, validators="check_input")
...     do_work = active.to.itself(on="risky_action")
...     error_execution = active.to(error_state)
...
...     def check_input(self, value=None, **kwargs):
...         if value is None:
...             raise ValueError("Input required")
...
...     def risky_action(self, **kwargs):
...         raise RuntimeError("Boom")

>>> sm = GuardedWithErrorHandler()

>>> sm.send("start")
Traceback (most recent call last):
    ...
ValueError: Input required

>>> "idle" in sm.configuration_values  # NOT in error_state
True

>>> sm.send("start", value="ok")
>>> "active" in sm.configuration_values
True

>>> sm.send("do_work")  # action error → goes to error_state
>>> "error_state" in sm.configuration_values
True

```

The validator rejection propagates directly to the caller, while the action
error in `risky_action()` is caught by the engine and routed through the
`error.execution` transition.


### Combining validators and conditions

Validators and conditions can be used together on the same transition.
Validators run **first** — if a validator rejects, conditions are never
evaluated:

```py
>>> class CombinedGuards(StateChart):
...     idle = State(initial=True)
...     active = State(final=True)
...
...     start = idle.to(active, validators="check_auth", cond="has_permission")
...
...     has_permission = True
...
...     def check_auth(self, token=None, **kwargs):
...         if token != "valid":
...             raise PermissionError("Invalid token")

>>> sm = CombinedGuards()

>>> sm.send("start", token="bad")
Traceback (most recent call last):
    ...
PermissionError: Invalid token

>>> sm.send("start", token="valid")
>>> "active" in sm.configuration_values
True

```

```{seealso}
See the example {ref}`sphx_glr_auto_examples_all_actions_machine.py` for
a complete demonstration of validator and condition resolution order.
```

```{hint}
In Python, specific values are considered **falsy** and evaluate as `False`
in a boolean context: `None`, `0`, `0.0`, empty strings, lists, tuples,
sets, and dictionaries, and instances of classes whose `__bool__()` or
`__len__()` returns `False` or `0`.

So `cond=lambda: []` evaluates as `False`.
```
