(behaviour)=
(statecharts)=

# Behaviour

The `StateChart` class follows the
[SCXML specification](https://www.w3.org/TR/scxml/) by default. The
`StateMachine` class extends `StateChart` but overrides several defaults to
preserve backward compatibility with existing code.

The behavioral differences are controlled by class-level attributes. This
design allows a gradual upgrade path: start from `StateMachine` and selectively
enable spec-compliant behaviors one at a time, or start from `StateChart` and
get full SCXML compliance out of the box.

```{tip}
We **strongly recommend** that new projects use `StateChart` directly. Existing
projects should consider migrating when possible, as the SCXML-compliant
behavior provides more predictable semantics.
```


## Comparison table

| Attribute                          | `StateChart`  | `StateMachine` | Description |
|------------------------------------|---------------|----------------|-------------|
| `allow_event_without_transition`   | `True`        | `False`        | Tolerate events that don't match any transition |
| `enable_self_transition_entries`   | `True`        | `False`        | Execute entry/exit actions on self-transitions |
| `atomic_configuration_update`      | `False`       | `True`         | When to update {ref}`configuration <querying-configuration>` during a microstep |
| `error_on_execution`              | `True`        | `False`        | Catch runtime errors as `error.execution` events |


## `allow_event_without_transition`

When `True` (SCXML default), sending an event that does not match any enabled
transition is silently ignored. When `False` (legacy default), a
`TransitionNotAllowed` exception is raised, including for unknown event names.

The SCXML spec requires tolerance to unmatched events, as the event-driven model
expects that not every event is relevant in every state.


## `enable_self_transition_entries`

When `True` (SCXML default), a {ref}`self-transition <self-transition>` executes
the state's exit and entry actions, just like any other transition. When `False`
(legacy default), self-transitions skip entry/exit actions.

The SCXML spec treats self-transitions as regular transitions that happen to
return to the same state, so entry/exit actions must fire. Use an
{ref}`internal transition <internal-transition>` if you need a transition that
stays in the same state **without** running exit/entry actions.


## `atomic_configuration_update`

When `False` (SCXML default), a microstep follows the SCXML processing order:
first exit all states in the exit set (running exit callbacks), then execute the
transition content (`on` callbacks), then enter all states in the entry set
(running entry callbacks). During the `on` callbacks, the
{ref}`configuration <querying-configuration>` may be empty or partial.

When `True` (legacy default), the configuration is updated atomically after the
`on` callbacks, so `sm.configuration` and `state.is_active` always reflect a
consistent snapshot during the transition. This was the behavior of all previous
versions.

```{note}
When `atomic_configuration_update` is `False`, `on` callbacks can request
`previous_configuration` and `new_configuration` keyword arguments to inspect
which states were active before and after the microstep. See
{ref}`dependency-injection` for the full parameter list.
```


## `error_on_execution`

When `True` (SCXML default), runtime exceptions in callbacks (guards, actions,
entry/exit) are caught by the engine and result in an internal `error.execution`
event. When `False` (legacy default), exceptions propagate normally to the
caller.

```{seealso}
See {ref}`error-handling` for the full `error.execution` lifecycle, block-level
error catching, and the cleanup/finalize pattern.
```


## Gradual migration

You can override any of these attributes individually. For example, to adopt
SCXML error handling in an existing `StateMachine` without changing other
behaviors:

```python
class MyMachine(StateMachine):
    error_on_execution = True
    # ... everything else behaves as before ...
```

Or to use `StateChart` but keep the legacy atomic configuration update:

```python
class MyChart(StateChart):
    atomic_configuration_update = True
    # ... SCXML-compliant otherwise ...
```

```{seealso}
See [](releases/upgrade_2x_to_3.md) for a complete migration guide from
`StateMachine` 2.x to `StateChart` 3.x.
```
