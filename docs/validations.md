(validations)=

# Validations

The library validates your statechart structure at two stages: **class
definition time** (when the Python class body is evaluated) and **instance
creation time** (when you call the constructor). These checks catch common
mistakes early — before any event is ever processed.

All validation errors raise `InvalidDefinition`.

```py
>>> from statemachine import StateChart, State
>>> from statemachine.exceptions import InvalidDefinition

```


## Class definition validations

These checks run as soon as the class body is evaluated by the
`StateMachineMetaclass`. If any check fails, the class itself is not
created.

```{note}
Statecharts loaded via {func}`statemachine.io.load` (SCXML/JSON/YAML) disable the three
**structural** checks below — unreachable states, trap states and final-state
reachability — because declarative documents legitimately express configurations they
would reject. See [](io/index.md#validation-of-loaded-documents).
```


### Exactly one initial state

Every statechart must have exactly one `initial` state at the root level:

```py
>>> try:
...     class Bad(StateChart):
...         a = State(initial=True)
...         b = State(initial=True)
...         go = a.to(b)
... except InvalidDefinition as e:
...     print(e)
There should be one and only one initial state. Your currently have these: a, b

```

### No transitions from final states

Final states represent completion — outgoing transitions are not allowed:

```py
>>> try:
...     class Bad(StateChart):
...         draft = State(initial=True)
...         closed = State(final=True)
...         reopen = closed.to(draft)
...         close = draft.to(closed)
... except InvalidDefinition as e:
...     print(e)
Cannot declare transitions from final state. Invalid state(s): ['closed']

```

(unreachable-states)=

### Unreachable states

Every state must be reachable from the initial state. Isolated states
indicate a wiring mistake:

```py
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

Disable with `validate_disconnected_states = False`.


(trap-states)=

### Trap states

Every non-final state must have at least one outgoing transition.
A state with no way out is a "trap" — likely a forgotten transition:

```py
>>> try:
...     class Bad(StateChart):
...         red = State(initial=True)
...         green = State()
...         hazard = State()
...         cycle = red.to(green) | green.to(red)
...         fault = red.to(hazard) | green.to(hazard)
... except InvalidDefinition as e:
...     print(e)
All non-final states should have at least one outgoing transition. These states have no outgoing transition: ['hazard']

```

Disable with `validate_trap_states = False`:

```py
>>> class Accepted(StateChart):
...     validate_trap_states = False
...     red = State(initial=True)
...     green = State()
...     hazard = State()
...     cycle = red.to(green) | green.to(red)
...     fault = red.to(hazard) | green.to(hazard)

```


### Final state reachability

When final states exist, every non-final state must have at least one path
to a final state:

```py
>>> try:
...     class Bad(StateChart):
...         draft = State(initial=True)
...         abandoned = State()
...         closed = State(final=True)
...         produce = draft.to(abandoned) | abandoned.to(abandoned)
...         close = draft.to(closed)
... except InvalidDefinition as e:
...     print(e)
All non-final states should have at least one path to a final state. These states have no path to a final state: ['abandoned']

```

Disable with `validate_final_reachability = False`.


(callback-name-conflicts)=

### Callback names bound to an event and to a state

A method name can match two naming conventions at once: `on_init_payment` is the action
of an event `init_payment` and also the {ref}`initial action <explicit-initial-transition>`
of a compound state `payment`. Such a method would run for both. When the class, its
model or a listener defines one, an `on_init_<state>` name raises `InvalidDefinition`:

```py
>>> try:
...     class Checkout(StateChart):
...         cart = State(initial=True)
...         class payment(State.Compound):
...             choosing = State()
...             paid = State(final=True)
...             pay = choosing.to(paid)
...         init_payment = cart.to(payment)
...
...         def on_init_payment(self):
...             pass
... except InvalidDefinition as e:
...     print(e)
Checkout defines on_init_payment, bound both to an event and to the initial transition of a compound state. Rename the event or the method.

```

The same overlap with `on_enter_<state>`, `on_exit_<state>` or `on_invoke_<state>` (an
event `enter_x` and a state `x`, for instance) emits a `DeprecationWarning` and will raise
in 4.0. Listeners are checked when they are attached, by the constructor or by
`add_listener()`.

Disable with `validate_callback_name_conflicts = False`; the method then runs for both.


### Internal transition targets

Internal transitions must target the same state (self) or a descendant —
they cannot cross to external states:

```py
>>> try:
...     class Bad(StateChart):
...         a = State(initial=True)
...         b = State(final=True)
...         go = a.to(b, internal=True)
... except InvalidDefinition as e:
...     assert "Not a valid internal transition" in str(e)

```

### Initial transitions have no conditions

Initial transitions (automatically generated for the initial state) cannot
carry conditions or events — they always fire unconditionally.


### `donedata` on final states only

The `donedata` parameter can only be used on states marked as `final=True`:

```py
>>> try:
...     class Bad(StateChart):
...         a = State(initial=True, donedata="get_data")
...         b = State(final=True)
...         go = a.to(b)
... except InvalidDefinition as e:
...     print(e)
'donedata' can only be specified on final states.

```


(callback-name-collision)=

### Callback names across nested state bodies

Callbacks declared inside a `State.Compound` or `State.Parallel` body are attached to the
statechart class under their own names, so nested bodies share one namespace with each other
and with the class body. A name reached by name (a naming convention such as
`on_enter_<state>`, a string reference such as `cond="ready"`, or a plain method called as
`self.ready()`) declared twice would keep only the last body:

```py
>>> try:
...     class Bad(StateChart):
...         class war(State.Parallel):
...             class quest(State.Compound):
...                 start = State(initial=True)
...                 end = State(final=True)
...                 go = start.to(end)
...
...                 def on_enter_end(self):
...                     print("quest")
...
...             class battle(State.Compound):
...                 fighting = State(initial=True)
...                 won = State(final=True)
...                 go = fighting.to(won)
...
...                 def on_enter_end(self):
...                     print("battle")
... except InvalidDefinition as e:
...     print(e)
Callback 'on_enter_end' is declared in both the 'quest' and the 'battle' state bodies. Nested state bodies share the class namespace. Rename one of them.

```

The same callable assigned under one name in several bodies is not a collision, and a nested
body may override a method inherited from a base class. A plain method named like an event or
another attribute of the class is also rejected. Callbacks attached through a decorator, or by
passing the function itself, may share a name, even with an event: each runs in the body that
declares it, as long as no naming convention, string reference or plain method uses that name.

### Invalid listener entries

Entries in the `listeners` class attribute must be classes, callables, or
object instances — not primitives like strings or numbers:

```py
>>> try:
...     class Bad(StateChart):
...         listeners = ["not_a_listener"]
...         a = State(initial=True)
...         b = State(final=True)
...         go = a.to(b)
... except InvalidDefinition as e:
...     assert "Invalid entry in 'listeners'" in str(e)

```


## Instance creation validations

These checks run when you instantiate a statechart (call `MyChart()`).
They verify that the runtime wiring is correct — callbacks resolve to
actual methods, boolean expressions parse, etc.


### Callback resolution

Every callback name declared on a transition or state (via `on`, `before`,
`after`, `enter`, `exit`, `cond`, etc.) must resolve to an actual attribute
on the statechart, model, or one of the registered listeners.

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

This validation ensures there are no typos in callback names. It checks all
sources in order: the statechart class itself, then the model (if
provided), then each listener.

```{note}
Convention-based callbacks (like `on_enter_<state>` or `before_<event>`)
are **not** validated — they are optional by design. Only explicitly
declared callback names (passed as strings to `on`, `cond`, etc.) are
checked.
```


### Boolean expression parsing

Guard conditions written as boolean expressions must be syntactically valid:

```py
>>> try:
...     class MyChart(StateChart):
...         a = State(initial=True)
...         b = State(final=True)
...         go = a.to(b, cond="valid_a and valid_b")
...         def valid_a(self):
...             return True
...         def valid_b(self):
...             return True
...     sm = MyChart()
...     sm.send("go")
... except InvalidDefinition:
...     pass  # would fail if expression didn't parse

>>> "b" in sm.configuration_values
True

```

Expressions support `and`, `or`, `not`, and parentheses. See
{ref}`guards` for the full syntax.


## Summary

| Validation                        | When            | Configurable               |
|-----------------------------------|-----------------|----------------------------|
| Exactly one initial state         | Class definition| No                         |
| No transitions from final states  | Class definition| No                         |
| Unreachable states                | Class definition| `validate_disconnected_states` |
| Trap states                       | Class definition| `validate_trap_states`     |
| Final state reachability          | Class definition| `validate_final_reachability` |
| Callback names bound twice        | Class definition, listeners | `validate_callback_name_conflicts` |
| Internal transition targets       | Class definition| No                         |
| Initial transitions have no cond  | Class definition| No                         |
| `donedata` on final states only   | Class definition| No                         |
| Invalid listener entries          | Class definition| No                         |
| Callback names in nested bodies   | Class definition| No                         |
| Callback resolution               | Instance creation | No                       |
| Boolean expression parsing        | Instance creation | No                       |

All configurable flags default to `True`. Set them to `False` on the class
to disable the corresponding check.
