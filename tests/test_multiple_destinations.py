# coding: utf-8
from __future__ import absolute_import, unicode_literals

import pytest
import mock

from statemachine import StateMachine, State


def test_transition_should_choose_final_state_on_multiple_possibilities(
        approval_machine, current_time):
    # given
    model = mock.MagicMock(
        state='requested',
        accepted_at=None,
        rejected_at=None,
        completed_at=None,
    )
    machine = approval_machine(model)

    model.is_ok.return_value = False

    # when
    assert machine.validate() == model

    # then
    assert model.rejected_at == current_time
    assert machine.is_rejected

    # given
    model.is_ok.return_value = True

    # when
    assert machine.retry() == model

    # then
    assert model.rejected_at is None
    assert machine.is_requested

    # when
    assert machine.validate() == model

    # then
    assert model.accepted_at == current_time
    assert machine.is_accepted


def test_should_raise_error_if_not_define_callback_in_multiple_destinations():
    class ApprovalMachine(StateMachine):
        requested = State('Requested', initial=True)
        accepted = State('Accepted')
        rejected = State('Rejected')

        validate = requested.to(accepted, rejected)

    machine = ApprovalMachine()

    with pytest.raises(ValueError) as e:
        machine.validate()

        assert 'desired state' in e.message


@pytest.mark.parametrize('return_value', [
    None,
    1,
    (2, 3),
    (4, 5, 6),
    ((7, 8), 9),
])
def test_should_raise_error_if_not_inform_state_in_multiple_destinations(return_value):
    class ApprovalMachine(StateMachine):
        requested = State('Requested', initial=True)
        accepted = State('Accepted')
        rejected = State('Rejected')

        @requested.to(accepted, rejected)
        def validate(self):
            return return_value

    machine = ApprovalMachine()

    with pytest.raises(ValueError) as e:
        machine.validate()

        assert 'desired state' in e.message


def test_should_raise_error_if_returned_state_is_not_a_possible_destination():
    class ApprovalMachine(StateMachine):
        requested = State('Requested', initial=True)
        accepted = State('Accepted')
        rejected = State('Rejected')

        @requested.to(accepted, rejected)
        def validate(self):
            return self.requested

    machine = ApprovalMachine()

    with pytest.raises(ValueError) as e:
        machine.validate()

        assert 'desired state' in e.message


def test_should_change_to_returned_state_on_multiple_destination():
    class ApprovalMachine(StateMachine):
        requested = State('Requested', initial=True)
        accepted = State('Accepted')
        rejected = State('Rejected')

        @requested.to(accepted, rejected)
        def validate(self):
            return self.accepted

    machine = ApprovalMachine()

    assert machine.validate() is None
