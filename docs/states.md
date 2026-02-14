
# States

{ref}`State`, as the name says, holds the representation of a state in a {ref}`StateChart`.

```{eval-rst}
.. autoclass:: statemachine.state.State
    :noindex:
```

```{seealso}
How to define and attach [](actions.md) to {ref}`States`.
```


## Initial state

A {ref}`StateChart` should have one and only one `initial` {ref}`state`.


The initial {ref}`state` is entered when the machine starts and the corresponding entering
state {ref}`actions` are called if defined.

## State Transitions

All states should have at least one transition to and from another state.

If any states are unreachable from the initial state, an `InvalidDefinition` exception will be thrown.

```py
>>> from statemachine import StateChart, State

>>> class TrafficLightMachine(StateChart):
...     "A workflow machine"
...     red = State('Red', initial=True, value=1)
...     green = State('Green', value=2)
...     orange = State('Orange', value=3)
...     hazard = State('Hazard', value=4)
...
...     cycle = red.to(green) | green.to(orange) | orange.to(red)
...     blink = hazard.to.itself()
Traceback (most recent call last):
...
InvalidDefinition: There are unreachable states. The statemachine graph should have a single component. Disconnected states: ['hazard']
```

`StateChart` will also check that all non-final states have an outgoing transition, and warn you if any states would result in
the statemachine becoming trapped in a non-final state with no further transitions possible.

```{note}
This will currently issue a warning, but can be turned into an exception by setting `strict_states=True` on the class.
```

```py
>>> from statemachine import StateChart, State

>>> class TrafficLightMachine(StateChart, strict_states=True):
...     "A workflow machine"
...     red = State('Red', initial=True, value=1)
...     green = State('Green', value=2)
...     orange = State('Orange', value=3)
...     hazard = State('Hazard', value=4)
...
...     cycle = red.to(green) | green.to(orange) | orange.to(red)
...     fault = red.to(hazard) | green.to(hazard) | orange.to(hazard)
Traceback (most recent call last):
...
InvalidDefinition: All non-final states should have at least one outgoing transition. These states have no outgoing transition: ['hazard']
```

```{warning}
`strict_states=True` will become the default behaviour in future versions.
```


(final-state)=
## Final state


You can explicitly set final states.
Transitions from these states are not allowed and will raise exceptions.

```py
>>> from statemachine import StateChart, State

>>> class CampaignMachine(StateChart):
...     "A workflow machine"
...     draft = State('Draft', initial=True, value=1)
...     producing = State('Being produced', value=2)
...     closed = State('Closed', final=True, value=3)
...
...     add_job = draft.to.itself() | producing.to.itself() | closed.to(producing)
...     produce = draft.to(producing)
...     deliver = producing.to(closed)
Traceback (most recent call last):
...
InvalidDefinition: Cannot declare transitions from final state. Invalid state(s): ['closed']

```

If you mark any states as final, `StateChart` will check that all non-final states have a path to reach at least one final state.

```{note}
This will currently issue a warning, but can be turned into an exception by setting `strict_states=True` on the class.
```

```py
>>> class CampaignMachine(StateChart, strict_states=True):
...     "A workflow machine"
...     draft = State('Draft', initial=True, value=1)
...     producing = State('Being produced', value=2)
...     abandoned = State('Abandoned', value=3)
...     closed = State('Closed', final=True, value=4)
...
...     add_job = draft.to.itself() | producing.to.itself()
...     produce = draft.to(producing)
...     abandon = producing.to(abandoned) | abandoned.to(abandoned)
...     deliver = producing.to(closed)
Traceback (most recent call last):
...
InvalidDefinition: All non-final states should have at least one path to a final state. These states have no path to a final state: ['abandoned']

```

```{warning}
`strict_states=True` will become the default behaviour in future versions.
```

You can query a list of all final states from your statemachine.

```py
>>> class CampaignMachine(StateChart):
...     "A workflow machine"
...     draft = State('Draft', initial=True, value=1)
...     producing = State('Being produced', value=2)
...     closed = State('Closed', final=True, value=3)
...
...     add_job = draft.to.itself() | producing.to.itself()
...     produce = draft.to(producing)
...     deliver = producing.to(closed)

>>> machine = CampaignMachine()

>>> machine.final_states
[State('Closed', id='closed', value=3, initial=False, final=True, parallel=False)]

>>> any(s in machine.final_states for s in machine.configuration)
False

```

## States from Enum types

{ref}`States` can also be declared from standard `Enum` classes.

For this, use {ref}`States (class)` to convert your `Enum` type to a list of {ref}`State` objects.


```{eval-rst}
.. automethod:: statemachine.states.States.from_enum
  :noindex:
```

```{seealso}
See the example {ref}`sphx_glr_auto_examples_enum_campaign_machine.py`.
```

## Compound states

```{versionadded} 3.0.0
```

Compound states contain inner child states, enabling hierarchical state machines.
Define them using the `State.Compound` inner class syntax:

```py
>>> from statemachine import State, StateChart

>>> class Journey(StateChart):
...     class shire(State.Compound):
...         bag_end = State(initial=True)
...         green_dragon = State()
...         visit_pub = bag_end.to(green_dragon)
...     road = State(final=True)
...     depart = shire.to(road)

>>> sm = Journey()
>>> set(sm.configuration_values) == {"shire", "bag_end"}
True

```

Entering a compound activates both the parent and its `initial` child. You can query
whether a state is compound using the `is_compound` property.

```{seealso}
See {ref}`compound-states` for full details, nesting, and `done.state` events.
```

## Parallel states

```{versionadded} 3.0.0
```

Parallel states activate all child regions simultaneously. Each region operates
independently. Define them using `State.Parallel`:

```py
>>> from statemachine import State, StateChart

>>> class WarOfTheRing(StateChart):
...     validate_disconnected_states = False
...     class war(State.Parallel):
...         class quest(State.Compound):
...             start = State(initial=True)
...             end = State(final=True)
...             go = start.to(end)
...         class battle(State.Compound):
...             fighting = State(initial=True)
...             won = State(final=True)
...             victory = fighting.to(won)

>>> sm = WarOfTheRing()
>>> "start" in sm.configuration_values and "fighting" in sm.configuration_values
True

```

```{seealso}
See {ref}`parallel-states` for full details and done events.
```

## History pseudo-states

```{versionadded} 3.0.0
```

A history pseudo-state records the active child of a compound state when it is exited.
Re-entering via the history state restores the previously active child. Import and use
`HistoryState` inside a `State.Compound`:

```py
>>> from statemachine import HistoryState, State, StateChart

>>> class WithHistory(StateChart):
...     validate_disconnected_states = False
...     class mode(State.Compound):
...         a = State(initial=True)
...         b = State()
...         h = HistoryState()
...         switch = a.to(b)
...     outside = State()
...     leave = mode.to(outside)
...     resume = outside.to(mode.h)

>>> sm = WithHistory()
>>> sm.send("switch")
>>> sm.send("leave")
>>> sm.send("resume")
>>> "b" in sm.configuration_values
True

```

Use `HistoryState(deep=True)` for deep history that remembers the exact leaf state
in nested compounds.

```{seealso}
See {ref}`history-states` for shallow vs deep history and default transitions.
```

## Configuration

```{versionadded} 3.0.0
```

The `configuration` property returns the set of currently active states as an
`OrderedSet[State]`. With compound and parallel states, multiple states can be
active simultaneously:

```py
>>> from statemachine import State, StateChart

>>> class Journey(StateChart):
...     class shire(State.Compound):
...         bag_end = State(initial=True)
...         green_dragon = State()
...         visit_pub = bag_end.to(green_dragon)
...     road = State(final=True)
...     depart = shire.to(road)

>>> sm = Journey()
>>> {s.id for s in sm.configuration} == {"shire", "bag_end"}
True

```

Use `configuration_values` for a set of the active state values (or IDs if no
custom value is defined):

```py
>>> set(sm.configuration_values) == {"shire", "bag_end"}
True

```

```{note}
The older `current_state` property is deprecated. Use `configuration` instead,
which works consistently for both flat and hierarchical state machines.
```
