# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import pytest

from .models import MyModel
from statemachine import State
from statemachine import StateMachine
from statemachine.statemachine import Transition


def test_transition_representation(campaign_machine):
    s = repr([t for t in campaign_machine.draft.transitions if t.event == "produce"][0])
    assert s == (
        "Transition("
        "State('Draft', id='draft', value='draft', initial=True, final=False), "
        "State('Being produced', id='producing', value='producing', "
        "initial=False, final=False), event='produce')"
    )


def test_list_machine_events(classic_traffic_light_machine):
    machine = classic_traffic_light_machine()
    transitions = [t.name for t in machine.events]
    assert transitions == ["go", "slowdown", "stop"]


def test_list_state_transitions(classic_traffic_light_machine):
    machine = classic_traffic_light_machine()
    events = [t.event for t in machine.green.transitions]
    assert events == ["slowdown"]


def test_transition_should_accept_decorator_syntax(traffic_light_machine):
    machine = traffic_light_machine()
    assert machine.current_state == machine.green


def test_transition_as_decorator_should_call_method_before_activating_state(
    traffic_light_machine,
):
    machine = traffic_light_machine()
    assert machine.current_state == machine.green
    assert (
        machine.cycle(1, 2, number=3, text="x") == "Running cycle from green to yellow"
    )
    assert machine.current_state == machine.yellow


@pytest.mark.parametrize(
    "machine_name",
    [
        "traffic_light_machine",
        "reverse_traffic_light_machine",
    ],
)
def test_cycle_transitions(request, machine_name):
    machine_class = request.getfixturevalue(machine_name)
    machine = machine_class()
    expected_states = ["green", "yellow", "red"] * 2
    for expected_state in expected_states:
        assert machine.current_state.id == expected_state
        machine.cycle()


def test_transition_call_can_only_be_used_as_decorator():
    source, dest = State("Source"), State("Destination")
    transition = Transition(source, dest)

    with pytest.raises(TypeError):
        transition("not a callable")


@pytest.fixture(params=["bounded", "unbounded"])
def transition_callback_machine(request):
    if request.param == "bounded":

        class ApprovalMachine(StateMachine):
            "A workflow"
            requested = State("Requested", initial=True)
            accepted = State("Accepted")

            validate = requested.to(accepted)

            def on_validate(self):
                self.model.calls.append("on_validate")
                return "accepted"

    elif request.param == "unbounded":

        class ApprovalMachine(StateMachine):
            "A workflow"
            requested = State("Requested", initial=True)
            accepted = State("Accepted")

            @requested.to(accepted)
            def validate(self):
                self.model.calls.append("on_validate")
                return "accepted"

    else:
        raise ValueError("machine not defined")

    return ApprovalMachine


def test_statemachine_transition_callback(transition_callback_machine):
    model = MyModel(state="requested", calls=[])
    machine = transition_callback_machine(model)
    assert machine.validate() == "accepted"
    assert model.calls == ["on_validate"]


def test_can_run_combined_transitions():
    class CampaignMachine(StateMachine):
        "A workflow machine"
        draft = State("Draft", initial=True)
        producing = State("Being produced")
        closed = State("Closed")

        abort = draft.to(closed) | producing.to(closed) | closed.to(closed)
        produce = draft.to(producing)

    machine = CampaignMachine()

    machine.abort()

    assert machine.closed.is_active


def test_transitions_to_the_same_estate_as_itself():
    class CampaignMachine(StateMachine):
        "A workflow machine"
        draft = State("Draft", initial=True)
        producing = State("Being produced")
        closed = State("Closed")

        update = draft.to.itself()
        abort = draft.to(closed) | producing.to(closed) | closed.to.itself()
        produce = draft.to(producing)

    machine = CampaignMachine()

    machine.update()

    assert machine.draft.is_active


class TestReverseTransition(object):
    @pytest.mark.parametrize(
        "initial_state",
        [
            "green",
            "yellow",
            "red",
        ],
    )
    def test_reverse_transition(self, reverse_traffic_light_machine, initial_state):
        machine = reverse_traffic_light_machine(start_value=initial_state)
        assert machine.current_state.id == initial_state

        machine.stop()

        assert machine.red.is_active


def test_should_transition_with_a_dict_as_return():
    "regression test that verifies if a dict can be used as return"

    expected_result = {
        "a": 1,
        "b": 2,
        "c": 3,
    }

    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State("Requested", initial=True)
        accepted = State("Accepted")
        rejected = State("Rejected")

        accept = requested.to(accepted)
        reject = requested.to(rejected)

        def on_accept(self):
            return expected_result

    machine = ApprovalMachine()

    result = machine.send("accept")
    assert result == expected_result
