# coding: utf-8
from __future__ import absolute_import, unicode_literals


import pytest
import mock

from statemachine import Transition, State, exceptions, StateMachine


def test_transition_representation(campaign_machine):
    s = repr([t for t in campaign_machine.transitions if t.identifier == 'produce'][0])
    print(s)
    assert s == (
        "Transition("
        "State('Draft', identifier='draft', value='draft', initial=True), "
        "(State('Being produced', identifier='producing', value='producing', "
        "initial=False),), identifier='produce')"
    )


def test_transition_should_accept_decorator_syntax(traffic_light_machine):
    machine = traffic_light_machine()
    assert machine.current_state == machine.green


def test_transition_as_decorator_should_call_method_before_activating_state(traffic_light_machine):
    machine = traffic_light_machine()
    assert machine.current_state == machine.green
    assert machine.slowdown(1, 2, number=3, text='x') == ((1, 2), {'number': 3, 'text': 'x'})
    assert machine.current_state == machine.yellow


def test_cycle_transitions(traffic_light_machine):
    machine = traffic_light_machine()
    expected_states = ['green', 'yellow', 'red'] * 2
    for expected_state in expected_states:
        assert machine.current_state.identifier == expected_state
        machine.cycle()


def test_transition_call_can_only_be_used_as_decorator():
    source, dest = State('Source'), State('Destination')
    transition = Transition(source, dest)

    with pytest.raises(exceptions.StateMachineError):
        transition('not a callable')


@pytest.fixture(params=['bounded', 'unbounded'])
def transition_callback_machine(request):
    if request.param == 'bounded':
        class ApprovalMachine(StateMachine):
            "A workflow"
            requested = State('Requested', initial=True)
            accepted = State('Accepted')

            validate = requested.to(accepted)

            def on_validate(self):
                self.model('on_validate')
                return 'accepted'
    elif request.param == 'unbounded':
        class ApprovalMachine(StateMachine):
            "A workflow"
            requested = State('Requested', initial=True)
            accepted = State('Accepted')

            @requested.to(accepted)
            def validate(self):
                self.model('on_validate')
                return 'accepted'
    else:
        raise ValueError('machine not defined')

    return ApprovalMachine


def test_statemachine_transition_callback(transition_callback_machine):
    model = mock.Mock(state='requested')
    machine = transition_callback_machine(model)
    assert machine.validate() == 'accepted'
    model.assert_called_once_with('on_validate')


def test_can_run_combined_transitions():
    class CampaignMachine(StateMachine):
        "A workflow machine"
        draft = State('Draft', initial=True)
        producing = State('Being produced')
        closed = State('Closed')

        abort = draft.to(closed) | producing.to(closed) | closed.to(closed)

    machine = CampaignMachine()

    machine.abort()

    assert machine.is_closed


def test_transitions_to_the_same_estate_as_itself():
    class CampaignMachine(StateMachine):
        "A workflow machine"
        draft = State('Draft', initial=True)
        producing = State('Being produced')
        closed = State('Closed')

        update = draft.to.itself()
        abort = draft.to(closed) | producing.to(closed) | closed.to.itself()

    machine = CampaignMachine()

    machine.update()

    assert machine.is_draft
