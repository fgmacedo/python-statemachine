
# States

A state in a state machine describes a particular behaviour of the machine.  When we say that
a machine is “in” a state, it means that the machine behaves in the way that state describes.



## Final States


You can explicitly set final states.
Transitions from these states are not allowed and will raise exception.

```py
>>> from statemachine import StateMachine, State

>>> from statemachine.exceptions import InvalidDefinition

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
InvalidDefinition: Final state does not should have defined transitions starting from that state

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
[State('Closed', identifier='closed', value=3, initial=False, final=True)]

```

```{seealso}
How to define and attach [](actions.md) to {ref}`States`.
```
