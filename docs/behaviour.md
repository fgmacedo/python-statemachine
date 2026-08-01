(behaviour)=
(statecharts)=

# Behaviour

```{seealso}
New to statecharts? See [](concepts.md) for an overview of how states,
transitions, events, and actions fit together.
```

The {class}`~statemachine.statemachine.StateChart` class follows the
[SCXML specification](https://www.w3.org/TR/scxml/) by default. The
{class}`~statemachine.statemachine.StateMachine` class extends `StateChart`
but overrides several defaults to preserve backward compatibility with
pre-3.0 code.

The behavioral differences are controlled by class-level attributes. This
design allows a gradual upgrade path: start from `StateMachine` and
selectively enable spec-compliant behaviors one at a time, or start from
`StateChart` and get full SCXML compliance out of the box.

```{tip}
We **strongly recommend** that new projects use `StateChart` directly.
Existing projects should consider migrating when possible, as the
SCXML-compliant behavior provides more predictable semantics.
```

```{warning}
This page describes runtime *semantics*. If you **load SCXML documents** via
`SCXMLProcessor`, note that SCXML is executable content: by default the
datamodel is evaluated with a restricted AST allowlist and `<script>` is
rejected, so untrusted documents cannot execute arbitrary code. Pass
`trusted=True` only for SCXML you control. See the 3.2.0 release notes and
GHSA-v4jc-pm6r-3vj8.
```


## Comparison table

| Attribute | `StateChart` | `StateMachine` | Description |
|---|---|---|---|
| `allow_event_without_transition` | `True` | `False` | Tolerate events that don't match any transition |
| `enable_self_transition_entries` | `True` | `False` | Execute entry/exit actions on self-transitions |
| `atomic_configuration_update` | `False` | `True` | When to update {ref}`configuration <querying-configuration>` during a microstep |
| `catch_errors_as_events` | `True` | `False` | Catch action errors as `error.execution` events |

Each attribute is described below, with cross-references to the pages that
cover the topic in depth.


## `allow_event_without_transition`

When `True` (SCXML default), sending an event that does not match any enabled
transition is silently ignored. When `False` (legacy default), a
`TransitionNotAllowed` exception is raised, including for unknown event names.

The SCXML spec requires tolerance to unmatched events, as the event-driven
model expects that not every event is relevant in every state.

```{seealso}
See {ref}`conditions` for how the engine selects transitions, and
{ref}`checking enabled events` to query which events are currently valid.
```


## `enable_self_transition_entries`

When `True` (SCXML default), a {ref}`self-transition <self-transition>`
executes the state's exit and entry actions, just like any other transition.
When `False` (legacy default), self-transitions skip entry/exit actions.

The SCXML spec treats self-transitions as regular transitions that happen to
return to the same state, so entry/exit actions must fire. Use an
{ref}`internal transition <internal-transition>` if you need a transition that
stays in the same state **without** running exit/entry actions.

```{seealso}
See {ref}`transitions` for the full reference on self-transitions and
internal transitions.
```


## `atomic_configuration_update`

Controls **when** the {ref}`configuration <querying-configuration>` is
updated during a microstep.

When `False` (SCXML default), the configuration reflects each phase as it
happens: states are removed during exit and added during entry. This means
that during transition `on` callbacks, the configuration may be empty or
partial — the source states have already been exited but the target states
have not yet been entered.

When `True` (legacy default), the configuration is updated atomically
**after** the `on` callbacks complete, so `sm.configuration` and
`state.is_active` always reflect a consistent snapshot during the transition.

```py
>>> from statemachine import State, StateChart

>>> class AtomicDemo(StateChart):
...     atomic_configuration_update = True
...     off = State(initial=True)
...     on = State(final=True)
...
...     switch = off.to(on, on="check_config")
...
...     def check_config(self):
...         # With atomic update, configuration is unchanged during 'on'
...         self.off_was_active = self.off.is_active
...         self.on_was_active = self.on.is_active

>>> sm = AtomicDemo()
>>> sm.send("switch")
>>> sm.off_was_active  # source still in configuration during 'on'
True
>>> sm.on_was_active  # target not yet in configuration during 'on'
False

```

With `atomic_configuration_update = False` (the SCXML default), the result
is different — `off.is_active` is `False` because exit already removed it,
and `on.is_active` is also `False` because entry hasn't added it yet.
In this mode, use `previous_configuration` and `new_configuration` to
inspect the full picture:

```py
>>> class SCXMLDemo(StateChart):
...     off = State(initial=True)
...     on = State(final=True)
...
...     switch = off.to(on, on="check_config")
...
...     def check_config(self, previous_configuration, new_configuration):
...         self.prev = {s.id for s in previous_configuration}
...         self.new = {s.id for s in new_configuration}

>>> sm = SCXMLDemo()
>>> sm.send("switch")
>>> sm.prev
{'off'}
>>> sm.new
{'on'}

```

```{seealso}
See {ref}`dependency-injection` for the full list of parameters available
in callbacks.
```


## `catch_errors_as_events`

When `True` (SCXML default), runtime exceptions in action callbacks
(entry/exit, transition `on`) are caught by the engine and dispatched as
internal `error.execution` events. When `False` (legacy default), exceptions
propagate normally to the caller.

This flag only governs exceptions raised **inside** an action callback. An event
that doesn't match any enabled transition is a different case, controlled by
{ref}`allow_event_without_transition <behaviour>` instead.

```{note}
{ref}`Validators <validators>` are **not** affected by this flag — they
always propagate exceptions to the caller, regardless of the
`catch_errors_as_events` setting. See {ref}`validators` for details.
```

```{seealso}
See {ref}`error-handling` for the full `error.execution` lifecycle,
block-level error catching, and the cleanup/finalize pattern.
```


## Gradual migration

All behavioral attributes can be overridden individually. This lets you
adopt SCXML semantics incrementally in an existing `StateMachine`:

```python
class MyMachine(StateMachine):
    catch_errors_as_events = True
    # ... everything else behaves as before ...
```

Or keep a specific legacy behavior while using `StateChart` for the rest:

```python
class MyChart(StateChart):
    atomic_configuration_update = True
    # ... SCXML-compliant otherwise ...
```

```{seealso}
See [](releases/upgrade_2x_to_3.md) for a complete migration guide from
`StateMachine` 2.x to `StateChart` 3.x.
```
