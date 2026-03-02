
# Integrations

(machinemixin)=
## MachineMixin

{ref}`Domain models` can inherit from `MachineMixin` to automatically instantiate
and bind a {ref}`StateChart` to any Python class. This is the foundation for
integrating state machines with ORMs and other domain objects.

```{seealso}
See the [MachineMixin API reference](api.md#machinemixin) for the full list of attributes.
```

### Example

Given this state machine:

```py
>>> from statemachine import StateChart, State

>>> from statemachine.mixins import MachineMixin

>>> class CampaignMachine(StateChart):
...     "A workflow machine"
...     draft = State('Draft', initial=True, value=1)
...     producing = State('Being produced', value=2)
...     closed = State('Closed', value=3, final=True)
...     cancelled = State('Cancelled', value=4, final=True)
...
...     add_job = draft.to.itself() | producing.to.itself()
...     produce = draft.to(producing)
...     deliver = producing.to(closed)
...     cancel = cancelled.from_(draft, producing)

```

You can attach it to a model by inheriting from `MachineMixin` and setting
`state_machine_name` to the fully qualified class name:

``` py
>>> from statemachine import registry
>>> registry.register(CampaignMachine)  # register for lookup by qualname
<class '...CampaignMachine'>
>>> registry._initialized = True  # skip Django autodiscovery in doctest

>>> class Workflow(MachineMixin):
...     state_machine_name = '__main__.CampaignMachine'
...     state_machine_attr = 'sm'
...     state_field_name = 'workflow_step'
...     bind_events_as_methods = True
...
...     workflow_step = 1

>>> model = Workflow()

>>> isinstance(model.sm, CampaignMachine)
True

>>> model.workflow_step
1

>>> model.sm.draft in model.sm.configuration
True

```

With `bind_events_as_methods = True`, events become methods on the model itself:

``` py
>>> model = Workflow()
>>> model.produce()
>>> model.workflow_step
2

>>> model.sm.cancel()  # you can still call the SM directly

>>> model.workflow_step
4

>>> model.sm.cancelled in model.sm.configuration
True

```

```{note}
In this example `state_machine_name` uses a `__main__` prefix because the class
is defined inline for doctest purposes. In your code, use the fully qualified
path (e.g., `'myapp.statemachines.CampaignMachine'`).
```

(django integration)=
## Django integration

When used in a Django App, this library implements an auto-discovery hook similar to how Django's
built-in **admin** [autodiscover](https://docs.djangoproject.com/en/dev/ref/contrib/admin/#django.contrib.admin.autodiscover).

> This library attempts to import a **statemachine** or **statemachines** module in each installed
> application. Such modules are expected to register `StateChart` classes to be used with
> the {ref}`MachineMixin`.


```{hint}
We advise keeping {ref}`StateChart` definitions in their own modules to avoid circular
references. If you place state machines in modules named `statemachine` or `statemachines`
inside installed Django Apps, they will be automatically imported and registered.

That said, nothing stops you from declaring your state machine alongside your models.
```


### Django example

```py
# campaign/statemachines.py

from statemachine import StateChart
from statemachine import State


class CampaignMachine(StateChart):
    "A workflow machine"
    draft = State('Draft', initial=True, value=1)
    producing = State('Being produced', value=2)
    closed = State('Closed', value=3)
    cancelled = State('Cancelled', value=4)

    add_job = draft.to.itself() | producing.to.itself()
    produce = draft.to(producing)
    deliver = producing.to(closed)
    cancel = cancelled.from_(draft, producing)
```

Integrate with your Django model using `MachineMixin`:

```py
# campaign/models.py

from django.db import models

from statemachine.mixins import MachineMixin


class Campaign(models.Model, MachineMixin):
    state_machine_name = 'campaign.statemachines.CampaignMachine'
    state_machine_attr = 'sm'
    state_field_name = 'step'

    name = models.CharField(max_length=30)
    step = models.IntegerField()
```

### Data migrations

Django's `apps.get_model()` returns **historical model** classes that are dynamically created
and don't carry user-defined class attributes like `state_machine_name`. Since version 2.6.0,
`MachineMixin` detects these historical models and gracefully skips state machine
initialization, so data migrations that use `apps.get_model()` work without errors.

```{note}
The state machine instance will **not** be available on historical model objects.
If your data migration needs to interact with the state machine, set the attributes
manually on the historical model class:

    def backfill_data(apps, schema_editor):
        MyModel = apps.get_model("myapp", "MyModel")
        MyModel.state_machine_name = "myapp.statemachines.MyStateMachine"
        for obj in MyModel.objects.all():
            obj.statemachine  # now available
```
