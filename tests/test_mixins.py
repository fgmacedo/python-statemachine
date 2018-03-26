# coding: utf-8

import pytest
from statemachine.mixins import MachineMixin


class MyModel(MachineMixin):
    state_machine_name = 'CampaignMachine'

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        super(MyModel, self).__init__()

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.__dict__)


def test_mixin_should_instantiate_a_machine(campaign_machine):
    model = MyModel(state='draft')
    assert isinstance(model.statemachine, campaign_machine)
    assert model.state == 'draft'
    assert model.statemachine.current_state == model.statemachine.draft


def test_mixin_should_raise_exception_if_machine_class_does_not_exist():
    class MyModelWithoutMachineName(MachineMixin):
        pass
    with pytest.raises(ValueError):
        MyModelWithoutMachineName()
