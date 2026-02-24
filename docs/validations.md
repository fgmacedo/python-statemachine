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
| Internal transition targets       | Class definition| No                         |
| Initial transitions have no cond  | Class definition| No                         |
| `donedata` on final states only   | Class definition| No                         |
| Invalid listener entries          | Class definition| No                         |
| Callback resolution               | Instance creation | No                       |
| Boolean expression parsing        | Instance creation | No                       |

All configurable flags default to `True`. Set them to `False` on the class
to disable the corresponding check.
