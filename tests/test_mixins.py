import pytest
from statemachine.mixins import MachineMixin

from tests.models import MyModel


class MyMixedModel(MyModel, MachineMixin):
    state_machine_name = "tests.conftest.CampaignMachine"


def test_mixin_should_instantiate_a_machine(campaign_machine):
    model = MyMixedModel(state="draft")
    assert isinstance(model.statemachine, campaign_machine)
    assert model.state == "draft"
    assert model.statemachine.current_state == model.statemachine.draft


def test_mixin_should_raise_exception_if_machine_class_does_not_exist():
    class MyModelWithoutMachineName(MachineMixin):
        pass

    with pytest.raises(ValueError, match="None is not a valid state machine name"):
        MyModelWithoutMachineName()


def test_mixin_should_skip_init_for_django_historical_models():
    """Regression test for #551: MachineMixin fails in Django data migrations.

    Django's ``apps.get_model()`` returns historical models with ``__module__ = '__fake__'``
    that don't carry user-defined class attributes like ``state_machine_name``.
    """

    # Simulate a Django historical model: __module__ is '__fake__' and
    # state_machine_name is not set (falls back to None from MachineMixin).
    HistoricalModel = type("HistoricalModel", (MachineMixin,), {"__module__": "__fake__"})

    instance = HistoricalModel()
    assert not hasattr(instance, "statemachine")
