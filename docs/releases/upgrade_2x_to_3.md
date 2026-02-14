# Upgrading from 2.x to 3.0

This guide covers all backward-incompatible changes in python-statemachine 3.0 and provides
step-by-step instructions for a smooth migration from the 2.x series.

```{tip}
Most 2.x code continues to work unchanged — the `StateMachine` class preserves backward-compatible
defaults. Review this guide to understand what changed and adopt the new APIs at your own pace.
```

## Quick checklist

1. Upgrade Python to 3.9+ (3.7 and 3.8 are no longer supported).
2. Replace `rtc=True/False` in constructors — the non-RTC model has been removed.
3. Replace `allow_event_without_transition` init parameter with a class-level attribute.
4. Replace `sm.current_state` with `sm.configuration`.
5. Replace `sm.add_observer(...)` with `sm.add_listener(...)`.
6. Update code that catches `TransitionNotAllowed` and accesses `.state` → use `.configuration`.
7. Review `on` callbacks that query `is_active` or `current_state` during transitions.

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
| `error_on_execution`              | `True`       | `False`        |

**Recommendation:** We recommend migrating to `StateChart` for new code. It follows the
[SCXML specification](https://www.w3.org/TR/scxml/) and enables powerful features like compound
states, parallel states, and structured error handling.

For existing code, you can continue using `StateMachine` — it works as before. You can also adopt
individual `StateChart` behaviors granularly by overriding class-level attributes:

```python
# Adopt SCXML error handling without switching to StateChart
class MyMachine(StateMachine):
    error_on_execution = True
    # ... rest of your definition unchanged
```

See {ref}`statecharts` for full details on each attribute.


## Remove the `rtc` parameter

The `rtc` parameter was deprecated in 2.3.2 and has been removed. All events are now queued before
processing (Run-to-Completion semantics).

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
`OrderedSet[State]`.

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


## Replace `add_observer()` with `add_listener()`

The method `add_observer` has been renamed to `add_listener`. The old name still works but emits
a `DeprecationWarning`.

**Before (2.x):**

```python
sm.add_observer(my_listener)
```

**After (3.0):**

```python
sm.add_listener(my_listener)
```


## Update `TransitionNotAllowed` exception handling

The `TransitionNotAllowed` exception now stores a `configuration` attribute (a set of states)
instead of a single `state` attribute, and the `event` attribute can be `None`.

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


## Configuration update timing during transitions

This is the most impactful behavioral change for existing code.

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
entry/exit on self-transitions).

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


## `send()` method — new parameters

The `send()` method has new optional parameters for delayed events and internal events:

```python
# 2.x signature
sm.send("event_name", *args, **kwargs)

# 3.0 signature (fully backward compatible)
sm.send("event_name", *args, delay=0, event_id=None, internal=False, **kwargs)
```

- `delay`: Time in milliseconds before the event is processed.
- `event_id`: Identifier for the event, used to cancel delayed events with `sm.cancel_event(event_id)`.
- `internal`: If `True`, the event is placed in the internal queue (processed in the current macrostep).

Existing code calling `sm.send("event")` works unchanged.


## `__repr__` output changed

The string representation now shows `configuration=[...]` instead of `current_state=...`:

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

```python
from statemachine import StateChart      # new base class
from statemachine import HistoryState    # history pseudo-state for compound states
from statemachine import StateMachine    # unchanged
from statemachine import State           # unchanged
from statemachine import Event           # unchanged
```


## New features overview

For full details on all new features, see the {ref}`3.0.0 release notes <StateMachine 3.0.0>`.
Here's a summary of what's new:

- **Compound states** — hierarchical state nesting with `State.Compound`
- **Parallel states** — concurrent regions with `State.Parallel`
- **History pseudo-states** — shallow and deep history with `HistoryState()`
- **Eventless (automatic) transitions** — transitions that fire when guard conditions are met
- **DoneData on final states** — final states can provide data to `done.state` handlers
- **Dynamic state machine creation** — `create_machine_class_from_definition()` from dicts
- **`In()` conditions** — check if a state is active in guard expressions
- **`prepare_event()` callback** — inject custom kwargs into all other callbacks
- **SCXML-compliant event matching** — wildcard events, dot notation
- **Error handling** — `error.execution` event for runtime exceptions
- **Delayed events** — `send(..., delay=500)` with cancellation support
- **`validate_disconnected_states` flag** — disable single-component graph validation
- **`is_terminated` property** — check if the state machine has reached a final state
- **`raise_()` method** — send events to the internal queue
- **`cancel_event()` method** — cancel delayed events by ID
