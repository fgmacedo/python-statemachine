# coding: utf-8

import mock
import pytest

from statemachine import StateMachine, State


class MyModel(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.__dict__)


class CampaignMachine(StateMachine):
    draft = State("Draft", initial=True)
    producing = State("Being produced")
    closed = State("Closed")

    add_job = draft.to(draft) | producing.to(producing)
    produce = draft.to(producing)
    deliver = producing.to(closed)

    def on_enter_producing(self, **kwargs):
        pass

    def on_exit_draft(self, **kwargs):
        pass


@pytest.fixture()
def on_enter_mock():
    with mock.patch.object(CampaignMachine, "on_enter_producing") as m:
        yield m


@pytest.fixture()
def on_exit_mock():
    with mock.patch.object(CampaignMachine, "on_exit_draft") as m:
        yield m


def test_run_transition_pass_arguments_to_sub_transitions(on_enter_mock, on_exit_mock):
    model = MyModel(state="draft")
    machine = CampaignMachine(model)

    machine.run("produce", param1="value1", param2="value2")

    assert model.state == "producing"
    on_enter_mock.assert_called_with(param1="value1", param2="value2")
    on_exit_mock.assert_called_with(param1="value1", param2="value2")
