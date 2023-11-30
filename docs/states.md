
# States

{ref}`State`, as the name says, holds the representation of a state in a {ref}`StateMachine`.

```{eval-rst}
.. autoclass:: statemachine.state.State
    :noindex:
```

```{seealso}
How to define and attach [](actions.md) to {ref}`States`.
```


## Initial state

A {ref}`StateMachine` should have one and only one `initial` {ref}`state`.


The initial {ref}`state` is entered when the machine starts and the corresponding entering
state {ref}`actions` are called if defined.

## State Transitions

All states should have at least one transition to and from another state.

If any states are unreachable from the initial state, an `InvalidDefinition` exception will be thrown.

```py
>>> from statemachine import StateMachine, State

>>> class TrafficLightMachine(StateMachine):
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

`StateMachine` will also check that all non-final states have an outgoing transition, and warn you if any states would result in
the statemachine becoming trapped in a non-final state with no further transitions possible.

```{note}
This will currently issue a warning, but can be turned into an exception by setting `strict_states=True` on the class.
```

```py
>>> from statemachine import StateMachine, State

>>> class TrafficLightMachine(StateMachine, strict_states=True):
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
>>> from statemachine import StateMachine, State

>>> class CampaignMachine(StateMachine):
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

If you mark any states as final, `StateMachine` will check that all non-final states have a path to reach at least one final state.

```{note}
This will currently issue a warning, but can be turned into an exception by setting `strict_states=True` on the class.
```

```py
>>> class CampaignMachine(StateMachine, strict_states=True):
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
>>> class CampaignMachine(StateMachine):
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
[State('Closed', id='closed', value=3, initial=False, final=True)]

>>> machine.current_state in machine.final_states
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
