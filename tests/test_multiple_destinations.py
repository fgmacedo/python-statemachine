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
        "A workflow"
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
    'requested'
])
def test_should_raise_error_if_not_inform_state_in_multiple_destinations(return_value):
    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State('Requested', initial=True)
        accepted = State('Accepted')
        rejected = State('Rejected')

        @requested.to(accepted, rejected)
        def validate(self):
            "tries to get an attr (like a desired state), failsback to the `return_value` itself"
            return getattr(self, str(return_value), return_value)

    machine = ApprovalMachine()

    with pytest.raises(ValueError) as e:
        machine.validate()

        assert 'desired state' in e.message


def test_should_change_to_returned_state_on_multiple_destination():
    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State('Requested', initial=True)
        accepted = State('Accepted')
        rejected = State('Rejected')

        @requested.to(accepted, rejected)
        def validate(self):
            return self.accepted

    machine = ApprovalMachine()

    assert machine.validate() is None
    assert machine.is_accepted


def test_should_change_to_returned_state_on_multiple_destination_with_combined_transitions():
    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State('Requested', initial=True)
        accepted = State('Accepted')
        rejected = State('Rejected')
        completed = State('Completed')

        validate = requested.to(accepted, rejected) | accepted.to(completed)
        retry = rejected.to(requested)

        @validate
        def do_validate(self):
            if not self.is_accepted:
                if self.model.is_ok():
                    return self.accepted
                else:
                    return self.rejected
            else:
                return 'congrats!'

    # given
    model = mock.MagicMock(state='requested')
    machine = ApprovalMachine(model)

    model.is_ok.return_value = False

    # when
    assert machine.validate() is None
    # then
    assert machine.is_rejected

    # given
    assert machine.retry() is None
    assert machine.is_requested
    model.is_ok.return_value = True

    # when
    assert machine.validate() is None
    # then
    assert machine.is_accepted

    # when
    assert machine.validate() == 'congrats!'
    # then
    assert machine.is_completed

    with pytest.raises(LookupError) as e:
        assert machine.validate()
        assert e.message == "Can't validate when in Completed."


def test_transition_on_execute_should_be_called_with_run_syntax(approval_machine, current_time):
    # given
    model = mock.MagicMock(state='requested', accepted_at=None,)
    machine = approval_machine(model)

    model.is_ok.return_value = True

    # when
    assert machine.run('validate') == model
    # then
    assert model.accepted_at == current_time
    assert machine.is_accepted
