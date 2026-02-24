# Upgrading from 2.x to 3.0

This guide covers all backward-incompatible changes in python-statemachine 3.0 and provides
step-by-step migration instructions from the 2.x series.

```{tip}
Most 2.x code continues to work unchanged — the `StateMachine` class preserves backward-compatible
defaults. Review this guide to understand what changed and adopt the new APIs at your own pace.
```

```{tip}
**Using an AI coding assistant?** You can use this guide as context for automated migration.
Try a prompt like:

> Update my usage of python-statemachine following this upgrade guide:
> https://python-statemachine.readthedocs.io/en/latest/releases/upgrade_2x_to_3.html
>
> Apply only the changes that are relevant to my codebase. Do not change working behavior.
```


## Quick checklist

1. Upgrade Python to 3.9+ (3.7 and 3.8 are no longer supported).
2. Replace `rtc=True/False` in constructors — the non-RTC model has been removed.
3. Replace `allow_event_without_transition` init parameter with a class-level attribute.
4. Replace `sm.current_state` with `sm.configuration` / `sm.configuration_values`.
5. Replace `sm.current_state.final` with `sm.is_terminated`.
6. Replace `sm.add_observer(...)` with `sm.add_listener(...)`.
7. Update code that catches `TransitionNotAllowed` and accesses `.state` → use `.configuration`.
8. Review `on` callbacks that query `is_active` or `current_state` during transitions.
9. If using `StateChart`, note that self-transitions now trigger entry/exit callbacks.
10. If using `States.from_enum`, note that `use_enum_instance` now defaults to `True`.
11. If using `get_machine_cls()` with short names, switch to fully-qualified names.
12. Remove `strict_states=True/False` — replace with `validate_trap_states` / `validate_final_reachability`.
13. Update code that parses `__repr__` output — format changed to `configuration=[...]`.

---


## Python compatibility

Support for Python 3.7 and 3.8 has been dropped. If you need these versions, stay on the 2.x
series.

StateMachine 3.0 supports Python 3.9, 3.10, 3.11, 3.12, 3.13, and 3.14.


## `StateChart` vs `StateMachine`

Version 3.0 introduces `StateChart` as the new base class. The existing `StateMachine` class is
now a subclass of `StateChart` with defaults that preserve 2.x behavior:

| Attribute                         | `StateChart` | `StateMachine` |
|-----------------------------------|:------------:|:--------------:|
| `allow_event_without_transition`  | `True`       | `False`        |
| `enable_self_transition_entries`  | `True`       | `False`        |
| `atomic_configuration_update`     | `False`      | `True`         |
| `catch_errors_as_events`              | `True`       | `False`        |

**Recommendation:** Use `StateChart` for new code. It follows the
[SCXML specification](https://www.w3.org/TR/scxml/) defaults — structured error handling,
self-transition entry/exit, and non-atomic configuration updates.

For existing code, you can continue using `StateMachine` — it works as before. You can also adopt
individual `StateChart` behaviors granularly by overriding class-level attributes:

**Before (2.x):**

```python
class MyMachine(StateMachine):
    ...
```

**After (3.0) — gradual adoption:**

```python
# Adopt SCXML error handling without switching to StateChart
class MyMachine(StateMachine):
    catch_errors_as_events = True
    # ... rest of your definition unchanged
```

See {ref}`behaviour` for full details on each attribute.


## Remove the `rtc` parameter

The `rtc` parameter was deprecated in 2.3.2 and has been removed. All events are now queued
before processing (Run-to-Completion semantics). See {ref}`rtc-model`.

**Before (2.x):**

```python
sm = MyMachine(rtc=False)  # synchronous, non-queued processing
```

**After (3.0):**

```python
sm = MyMachine()  # RTC is always enabled, remove the parameter
```

If you were passing `rtc=True` (the default), simply remove the parameter.


## `allow_event_without_transition` moved to class level

This was previously an `__init__` parameter and is now a class-level attribute.

**Before (2.x):**

```python
sm = MyMachine(allow_event_without_transition=True)
```

**After (3.0):**

```python
class MyMachine(StateMachine):
    allow_event_without_transition = True
    # ... states and transitions
```

```{note}
`StateMachine` defaults to `False` (same as 2.x). `StateChart` defaults to `True`.
```


## `current_state` deprecated — use `configuration`

Due to compound and parallel states, the state machine can now have multiple active states. The
`current_state` property is deprecated in favor of `configuration`, which always returns an
`OrderedSet[State]`. See {ref}`querying-configuration`.

**Before (2.x):**

```python
state = sm.current_state          # returns a single State
value = sm.current_state.value    # get the value
```

**After (3.0):**

```python
states = sm.configuration             # returns OrderedSet[State]
values = sm.configuration_values       # returns OrderedSet of values

# If you know you have a single active state (flat machine):
state = next(iter(sm.configuration))   # get the single State
```

```{tip}
For flat state machines (no compound/parallel states), `current_state_value` still returns a
single value and works as before. But we strongly recommend using `configuration` /
`configuration_values` for forward compatibility.
```


## Replace `current_state.final` with `is_terminated`

The old `current_state.final` pattern still works for flat state machines, but `is_terminated`
is the recommended replacement — it works correctly for all topologies (flat, compound, and
parallel), where "terminated" means all regions have reached a final state.
See {ref}`checking-termination`.

**Before (2.x):**

```python
if sm.current_state.final:
    print("done")

while not sm.current_state.final:
    sm.send("next")
```

**After (3.0):**

```python
if sm.is_terminated:
    print("done")

while not sm.is_terminated:
    sm.send("next")
```


## Replace `add_observer()` with `add_listener()`

The method `add_observer` has been removed in v3.0. Use `add_listener` instead.

For new code, consider using class-level listener declarations — they attach listeners
automatically to every instance and support a `setup()` protocol for dependency injection.
See {ref}`listeners`.

**Before (2.x):**

```python
sm.add_observer(my_listener)
```

**After (3.0) — runtime attachment:**

```python
sm.add_listener(my_listener)
```

**After (3.0) — class-level declaration (recommended for new code):**

```python
class MyMachine(StateChart):
    listeners = [MyListener]
    # ... states and transitions
```


## Update `TransitionNotAllowed` exception handling

`TransitionNotAllowed` is raised when an event has no valid transition from the current
configuration. Note that this exception only applies when `allow_event_without_transition`
is `False` (the `StateMachine` default). In `StateChart`, events without matching
transitions are discarded — this follows the SCXML recommendation, where statecharts
are reactive systems and not every event is expected to be handled in every state.

The exception now stores a `configuration` attribute (a set of states) instead of a single
`state` attribute, and the `event` attribute can be `None`.

**Before (2.x):**

```python
try:
    sm.send("go")
except TransitionNotAllowed as e:
    print(e.event)   # Event instance
    print(e.state)   # single State
```

**After (3.0):**

```python
try:
    sm.send("go")
except TransitionNotAllowed as e:
    print(e.event)           # Event instance or None
    print(e.configuration)   # MutableSet[State]
```

```{tip}
If you are migrating to `StateChart`, consider handling errors as events instead of
catching exceptions. With `catch_errors_as_events=True` (the default in `StateChart`),
runtime errors are dispatched as `error.execution` events that you can handle with
transitions. See {ref}`error-execution`.
```


## Configuration update timing during transitions

This is the most impactful behavioral change for existing code. See {ref}`behaviour` for
full details on `atomic_configuration_update`.

**In 2.x**, the active state was updated atomically _after_ the transition `on` callbacks,
meaning `sm.current_state` and `state.is_active` reflected the **source** state during `on`
callbacks.

**In 3.0** (SCXML-compliant behavior in `StateChart`), states are exited _before_ `on` callbacks
and entered _after_, so during `on` callbacks the configuration may be **empty**.

```{important}
If you use `StateMachine` (not `StateChart`), the default `atomic_configuration_update=True`
**preserves the 2.x behavior**. This section only affects code using `StateChart` or
`StateMachine` with `atomic_configuration_update=False`.
```

**Before (2.x):**

```python
def on_validate(self):
    if self.accepted.is_active:    # True during on callback in 2.x
        return "congrats!"
```

**After (3.0):**

Two new keyword arguments are available in `on` callbacks to inspect the transition context:

```python
def on_validate(self, previous_configuration, new_configuration):
    if self.accepted in previous_configuration:
        return "congrats!"
```

- `previous_configuration`: the set of states that were active before the microstep.
- `new_configuration`: the set of states that will be active after the microstep.

To restore the old behavior globally, set the class attribute:

```python
class MyChart(StateChart):
    atomic_configuration_update = True  # restore 2.x behavior
```

Or simply use `StateMachine`, which has `atomic_configuration_update=True` by default.


## Self-transition entry/exit behavior

In `StateChart`, self-transitions (a state transitioning to itself) now execute entry and exit
actions, following the SCXML spec. In `StateMachine`, the 2.x behavior is preserved (no
entry/exit on self-transitions). See {ref}`self-transition`.

**Before (2.x):**

```python
# Self-transitions did NOT trigger on_enter_*/on_exit_* callbacks
loop = s1.to.itself()
```

**After (3.0 with `StateChart`):**

```python
# Self-transitions DO trigger on_enter_*/on_exit_* callbacks
loop = s1.to.itself()

# To disable (preserve 2.x behavior):
class MyChart(StateChart):
    enable_self_transition_entries = False
```


## `States.from_enum` default changed to `use_enum_instance=True`

In 2.x, `States.from_enum` defaulted to `use_enum_instance=False`, meaning state values were the
raw enum values (e.g., integers). In 3.0, the default is `True`, so state values are the enum
instances themselves. See {ref}`states from enum types`.

**Before (2.x):**

```python
states = States.from_enum(MyEnum, initial=MyEnum.start)
# states.start.value == 1  (raw value)
```

**After (3.0):**

```python
states = States.from_enum(MyEnum, initial=MyEnum.start)
# states.start.value == MyEnum.start  (enum instance)
```

If your code relies on raw enum values, pass `use_enum_instance=False` explicitly.


## Short registry names removed

In 2.x, state machine classes were registered both by their fully-qualified name and their short
class name. The short-name lookup was deprecated since v0.8 and has been removed in 3.0.

**Before (2.x):**

```python
from statemachine.registry import get_machine_cls

cls = get_machine_cls("MyMachine")  # short name — worked with warning
```

**After (3.0):**

```python
from statemachine.registry import get_machine_cls

cls = get_machine_cls("myapp.machines.MyMachine")  # fully-qualified name
```


## `strict_states` removed — use `validate_trap_states` / `validate_final_reachability`

The `strict_states` class parameter has been removed. The two validations it controlled are now
always-on by default, each controlled by its own class-level attribute.
See {ref}`validations`.

**Before (2.x) — `s2` is a trap state (no outgoing transitions, not marked `final`):**

```python
class MyMachine(StateMachine, strict_states=False):
    s1 = State(initial=True)
    s2 = State()          # trap state — no outgoing transitions, not final
    go = s1.to(s2)
```

**After (3.0) — recommended: fix the definition by marking terminal states as `final`:**

```python
class MyMachine(StateMachine):
    s1 = State(initial=True)
    s2 = State(final=True)        # was State() — now correctly marked as final
    go = s1.to(s2)
```

**After (3.0) — opt out if you intentionally have non-final trap states:**

```python
class MyMachine(StateMachine):
    validate_trap_states = False           # allow non-final states without outgoing transitions
    validate_final_reachability = False    # allow non-final states without path to final
    s1 = State(initial=True)
    s2 = State()
    go = s1.to(s2)
```

The two flags are independent — you can disable one while keeping the other enabled.


## `send()` method — new parameters

The `send()` method has new optional parameters for delayed events and internal events.
Existing code calling `sm.send("event")` works unchanged. See {ref}`sending-events`.

**Before (2.x):**

```python
sm.send("event_name", *args, **kwargs)
```

**After (3.0) — fully backward compatible:**

```python
sm.send("event_name", *args, delay=0, send_id=None, internal=False, **kwargs)
```

- `delay`: Time in milliseconds before the event is processed.
- `send_id`: Identifier for the event, used to cancel delayed events with `sm.cancel_event(send_id)`.
- `internal`: If `True`, the event is placed in the internal queue (processed in the current macrostep).


## `__repr__` output changed

The string representation now shows `configuration=[...]` instead of `current_state=...`.

**Before (2.x):**

```
MyMachine(model=Model(), state_field='state', current_state='initial')
```

**After (3.0):**

```
MyMachine(model=Model(), state_field='state', configuration=['initial'])
```


## New public exports

The package now exports two additional symbols:

**Before (2.x):**

```python
from statemachine import StateMachine, State, Event
```

**After (3.0):**

```python
from statemachine import StateChart      # new base class
from statemachine import HistoryState    # history pseudo-state for compound states
from statemachine import StateMachine    # unchanged
from statemachine import State           # unchanged
from statemachine import Event           # unchanged
```


## What's new

For full details on all new features in 3.0 — including compound states, parallel states,
invoke, error handling, and more — see the
{ref}`3.0.0 release notes <StateMachine 3.0.0>`.
