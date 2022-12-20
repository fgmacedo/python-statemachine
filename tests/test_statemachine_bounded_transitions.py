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


@pytest.fixture
def event_mock():
    return mock.MagicMock()


@pytest.fixture
def state_machine(event_mock):
    class CampaignMachine(StateMachine):
        draft = State("Draft", initial=True)
        producing = State("Being produced")
        closed = State("Closed")

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)
        deliver = producing.to(closed)

        def on_enter_producing(self, *args, **kwargs):
            event_mock.on_enter_producing(*args, **kwargs)

        def on_exit_draft(self, **kwargs):
            event_mock.on_exit_draft(**kwargs)

        def on_enter_closed(self):
            event_mock.on_enter_closed()

        def on_exit_producing(self):
            event_mock.on_exit_producing()

    return CampaignMachine


def test_run_transition_pass_arguments_to_sub_transitions(
    state_machine,
    event_mock,
):
    model = MyModel(state="draft")
    machine = state_machine(model)

    machine.run("produce", param1="value1", param2="value2")

    assert model.state == "producing"
    event_mock.on_enter_producing.assert_called_with(param1="value1", param2="value2")
    event_mock.on_exit_draft.assert_called_with(param1="value1", param2="value2")

    machine.run("deliver", param3="value3")

    event_mock.on_enter_closed.assert_called_with()
    event_mock.on_exit_producing.assert_called_with()
