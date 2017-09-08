# coding: utf-8
from __future__ import absolute_import, unicode_literals

import pytest
import mock

from statemachine import StateMachine, State, exceptions


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

    with pytest.raises(exceptions.MultipleStatesFound) as e:
        machine.validate()

        assert 'desired state' in e.message


@pytest.mark.parametrize('return_value, expected_exception', [
    (None, exceptions.MultipleStatesFound),
    (1, exceptions.MultipleStatesFound),
    ((2, 3), exceptions.MultipleStatesFound),
    ((4, 5, 6), exceptions.MultipleStatesFound),
    (((7, 8), 9), exceptions.MultipleStatesFound),
    ('requested', exceptions.InvalidDestinationState),
])
def test_should_raise_error_if_not_inform_state_in_multiple_destinations(
        return_value, expected_exception):
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

    with pytest.raises(expected_exception) as e:
        machine.validate()

        assert 'desired state' in e.message


@pytest.mark.parametrize('callback', ['single', 'multiple'])
@pytest.mark.parametrize('with_return_value', [True, False], ids=['with_return', 'without_return'])
@pytest.mark.parametrize('return_value', [None, 'spam'])
def test_should_transition_to_the_state_returned_by_callback(
        callback, with_return_value, return_value):
    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State('Requested', initial=True)
        accepted = State('Accepted')
        rejected = State('Rejected')

        @requested.to(accepted)
        def transition_with_single_destination(self):
            if with_return_value:
                return return_value, self.accepted
            else:
                return self.accepted

        @requested.to(accepted, rejected)
        def transition_with_multiple_destination(self):
            if with_return_value:
                return return_value, self.accepted
            else:
                return self.accepted

    machine = ApprovalMachine()

    transition = 'transition_with_{}_destination'.format(callback)

    result = machine.run(transition)
    if with_return_value:
        assert result == return_value
    else:
        assert result is None
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

    with pytest.raises(exceptions.TransitionNotAllowed) as e:
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


def test_multiple_transition_callbacks():
    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State('Requested', initial=True)
        accepted = State('Accepted')

        @requested.to(accepted)
        def validate(self):
            return self.accepted

        def on_validate(self):
            return self.accepted

    machine = ApprovalMachine()

    with pytest.raises(exceptions.MultipleTransitionCallbacksFound):
        machine.validate()
