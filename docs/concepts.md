(concepts)=

# Core concepts

A statechart organizes behavior around **states**, **transitions**, and
**events**. Together they describe *when* the system can change, *what*
triggers the change, and *what happens* as a result.

```py
>>> from statemachine import StateChart, State

>>> class Turnstile(StateChart):
...     locked = State(initial=True)
...     unlocked = State()
...
...     coin = locked.to(unlocked, on="thank_you")
...     push = unlocked.to(locked)
...
...     def thank_you(self):
...         return "Welcome!"

>>> sm = Turnstile()
>>> sm.coin()
'Welcome!'

```

Even in this minimal example, the core concepts appear:

| Concept | What it is | Declared as |
|---|---|---|
| {ref}`StateChart <statechart>` | The container and runtime for the machine | `class MyChart(StateChart)` |
| {ref}`State <states>` | A mode or condition of the system | `State()`, `State.Compound`, `State.Parallel` |
| {ref}`Transition <transitions>` | A link from source state to target state | `source.to(target)`, `target.from_(source)` |
| {ref}`Event <events>` | A signal that triggers transitions | Class-level assignment or `Event(...)` |
| {ref}`Action <actions>` | A side-effect during state changes | `on`, `before`, `after`, `enter`, `exit` callbacks |
| {ref}`Condition <conditions>` | A guard that allows/blocks a transition | `cond`, `unless`, `validators` parameters |
| {ref}`Listener <listeners>` | An external observer of the lifecycle | `listeners = [...]` class attribute |

Each concept below introduces the idea briefly; follow the "See also" links
for the full reference. Listeners are covered in {ref}`their own page <listeners>`.

(concepts-statechart)=

## StateChart

A {ref}`StateChart <statechart>` is the container for states, transitions,
and events. It defines the topology (which states exist and how they
connect) and provides the runtime API — sending events, querying the
current configuration, and managing listeners.

In the turnstile example, `Turnstile` is the `StateChart`. After
instantiation, `sm` holds the runtime state and exposes methods like
`sm.send("coin")`, `sm.configuration`, and `sm.allowed_events`.

```{seealso}
See [](statechart.md) for the full reference: creating instances, sending
events, querying configuration, checking termination, and managing
listeners at runtime.
```


(concepts-states)=

## States

A **state** describes what the system is doing right now. At any point in
time, a statechart is "in" one or more states — the **configuration**. States
determine which transitions are available and which events are accepted.

In the turnstile example, `locked` and `unlocked` are the two possible
states. The machine starts in `locked` (its **initial state**) and can only
reach `unlocked` when the `coin` event fires.

```{seealso}
See [](states.md) for the full reference: initial and final states, compound
(nested) states, parallel regions, history pseudo-states, and more.
```


(concepts-transitions)=

## Transitions

A **transition** is a link between a **source** state and a **target** state.
When a transition fires, the system leaves the source and enters the target.
Transitions can carry {ref}`actions <actions>` (side-effects) and
{ref}`conditions <conditions>` (guards that must be satisfied).

In the turnstile, `locked.to(unlocked)` is a transition: it moves the system
from `locked` to `unlocked` and runs the `thank_you` action along the way.

```{seealso}
See [](transitions.md) for the full reference: declaring transitions,
self-transitions, internal transitions, eventless (automatic) transitions,
and more.
```


(concepts-events)=

## Events

An **event** is a signal that something has happened. Events trigger
transitions — without an event, a transition will not fire (unless it is
an {ref}`eventless <eventless>` transition with a guard condition).

In the turnstile, `coin` and `push` are events. When you call `sm.coin()` or
`sm.send("coin")`, the engine looks for a matching transition from the current
state and fires it. Events are processed following a **run-to-completion**
model — each event is fully handled before the next one starts.

```{seealso}
See [](events.md) for the full reference: declaring, triggering, scheduling,
and naming conventions. See [](processing_model.md) for how macrosteps and
microsteps work under the hood.
```


(concepts-actions)=

## Actions

An **action** is a side-effect that runs during a transition or on
entry/exit of a state. Actions are how the statechart interacts with the
outside world — sending notifications, updating a database, logging,
or returning a value.

In the turnstile, `thank_you` is an action attached to the `coin` transition
via the `on` parameter.

```{seealso}
See [](actions.md) for the full reference: callback naming conventions,
execution order, dependency injection, and all available hooks.
```


(concepts-conditions)=

## Conditions

A **condition** (also called a **guard**) is a predicate that must evaluate
to `True` for a transition to fire. A **validator** is similar but raises an
exception to block the transition instead of silently preventing it.

Conditions let you have multiple transitions for the same event, each with a
different guard — the first one that passes wins.

```{seealso}
See [](guards.md) for the full reference: `cond`, `unless`, `validators`,
boolean expressions, and checking enabled events.
```
