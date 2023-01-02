
# Mixins

Your model can inherited from a custom mixin to auto-instantiate a state machine.

## MachineMixin


```{eval-rst}
.. autoclass:: statemachine.mixins.MachineMixin
    :members:
    :undoc-members:
```

### Mixins example

Given a statemachine definition:

```py
>>> from statemachine import StateMachine, State

>>> from statemachine.mixins import MachineMixin

>>> class CampaignMachineWithKeys(StateMachine):
...     "A workflow machine"
...     draft = State('Draft', initial=True, value=1)
...     producing = State('Being produced', value=2)
...     closed = State('Closed', value=3)
...     cancelled = State('Cancelled', value=4)
...
...     add_job = draft.to.itself() | producing.to.itself()
...     produce = draft.to(producing)
...     deliver = producing.to(closed)
...     cancel = cancelled.from_(draft, producing)

```

It can be attached to a model using mixin and the full qualified name of the
class.

```{warning}
On this example the `state_machine_name` is receiving a `__main__` module due
to the way `autodoc` works so we can have automated testes on the docs
examples.

On your code, use the fully qualified path to the statemachine class.
```

``` py
>>> class MyModel(MachineMixin):
...     state_machine_name = '__main__.CampaignMachineWithKeys'
...
...     def __init__(self, **kwargs):
...         for k, v in kwargs.items():
...             setattr(self, k, v)
...         super(MyModel, self).__init__()
...
...     def __repr__(self):
...         return "{}({!r})".format(type(self).__name__, self.__dict__)

>>> model = MyModel(state=1)

>>> isinstance(model.statemachine, CampaignMachineWithKeys)
True

>>> model.state
1

>>> model.statemachine.current_state == model.statemachine.draft
True

>>> model.statemachine.cancel()

>>> model.state
4

>>> model.statemachine.current_state == model.statemachine.cancelled
True

```

```{seealso}
The [](integrations.md#django-integration) section.
```
