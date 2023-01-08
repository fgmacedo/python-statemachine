
# States

State, as the name sais, holds the representation of a state in a statemachine.


## State

```{eval-rst}
.. autoclass:: statemachine.state.State
    :members:
```


(final-state)=
### Final state


You can explicitly set final states.
Transitions from these states are not allowed and will raise exception.

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

You can retrieve all final states.

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

```

```{seealso}
How to define and attach [](actions.md) to {ref}`States`.
```
