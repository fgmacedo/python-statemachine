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
