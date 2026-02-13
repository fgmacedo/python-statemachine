
# Integrations

## Django integration

When used in a Django App, this library implements an auto-discovery hook similar to how Django's
built-in **admin** [autodiscover](https://docs.djangoproject.com/en/dev/ref/contrib/admin/#django.contrib.admin.autodiscover).

> This library attempts to import an **statemachine** or **statemachines** module in each installed
> application. Such modules are expected to register `StateMachine` classes to be used with
> the {ref}`MachineMixin`.


```{hint}
When using `python-statemachine` to control the state of a Django model, we advise keeping the
{ref}`StateMachine` definitions on their own modules.

So as circular references may occur, and as a way to help you organize your
code, if you put state machines on modules named as mentioned above inside installed
Django Apps, these {ref}`StateMachine` classes will be automatically
imported and registered.

This is only an advice, nothing stops you do declare your state machine alongside your models.
```


### Example

Given this StateMachine:

```py
# campaign/statemachines.py

from statemachine import StateMachine
from statemachine import State
from statemachine.mixins import MachineMixin


class CampaignMachineWithKeys(StateMachine):
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

Integrate with your model:

```py
# campaign/models.py

from django.db import models

class Campaign(models.Model, MachineMixin):
    state_machine_name = 'campaign.statemachines.CampaignMachineWithKeys'
    state_machine_attr = 'sm'
    state_field_name = 'step'

    name = models.CharField(max_length=30)
    step = models.IntegerField()
```


```{seealso}
Learn more about using the [](mixins.md#machinemixin).
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
