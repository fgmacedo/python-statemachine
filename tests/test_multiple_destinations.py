# coding: utf-8
from __future__ import absolute_import, unicode_literals

import pytest

from statemachine import StateMachine, State, exceptions


class Request(object):
    def __init__(self, state="requested"):
        self.state = None
        self._is_ok = False

    def is_ok(self):
        return self._is_ok


def test_transition_should_choose_final_state_on_multiple_possibilities(
    approval_machine, current_time
):
    # given
    model = Request()
    machine = approval_machine(model)

    model._is_ok = False

    # when
    assert machine.validate() == model

    # then
    assert model.rejected_at == current_time
    assert machine.is_rejected

    # given
    model._is_ok = True

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


def test_transition_to_first_that_executes_if_multiple_destinations():
    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State("Requested", initial=True)
        accepted = State("Accepted")
        rejected = State("Rejected")

        validate = requested.to(accepted, rejected)

    machine = ApprovalMachine()

    machine.validate()
    assert machine.is_accepted


def test_do_not_transition_if_multiple_destinations_with_guard():
    def never_will_pass(event_data):
        return False

    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State("Requested", initial=True)
        accepted = State("Accepted")
        rejected = State("Rejected")

        validate = (
            requested.to(accepted, conditions=never_will_pass)
            | requested.to(rejected, conditions="also_never_will_pass")
            | requested.to(requested, conditions="this_also_never_will_pass")
        )

        @property
        def also_never_will_pass(self):
            return False

        def this_also_never_will_pass(self, event_data):
            return False

    machine = ApprovalMachine()

    with pytest.raises(exceptions.TransitionNotAllowed):
        machine.validate()
    assert machine.is_requested


def test_check_invalid_reference_to_conditions():
    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State("Requested", initial=True)
        accepted = State("Accepted")
        rejected = State("Rejected")

        validate = requested.to(
            accepted, conditions="not_found_condition"
        ) | requested.to(rejected)

    with pytest.raises(exceptions.InvalidDefinition):
        ApprovalMachine()


def test_should_change_to_returned_state_on_multiple_destination_with_combined_transitions():
    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State("Requested", initial=True)
        accepted = State("Accepted")
        rejected = State("Rejected")
        completed = State("Completed")

        validate = (
            requested.to(accepted, conditions="is_ok")
            | requested.to(rejected)
            | accepted.to(completed)
        )
        retry = rejected.to(requested)

        def on_validate(self):
            if self.is_accepted and self.model.is_ok():
                return "congrats!"

    # given
    model = Request()
    machine = ApprovalMachine(model)

    model._is_ok = False

    # when
    assert machine.validate() is None
    # then
    assert machine.is_rejected

    # given
    assert machine.retry() is None
    assert machine.is_requested
    model._is_ok = True

    # when
    assert machine.validate() is None
    # then
    assert machine.is_accepted

    # when
    assert machine.validate() == "congrats!"
    # then
    assert machine.is_completed

    with pytest.raises(exceptions.TransitionNotAllowed) as e:
        assert machine.validate()
        assert e.message == "Can't validate when in Completed."


def test_transition_on_execute_should_be_called_with_run_syntax(
    approval_machine, current_time
):
    # given
    model = Request()
    machine = approval_machine(model)

    model._is_ok = True

    # when
    assert machine.run("validate") == model
    # then
    assert model.accepted_at == current_time
    assert machine.is_accepted


def test_multiple_values_returned_with_multiple_destinations():
    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State("Requested", initial=True)
        accepted = State("Accepted")
        denied = State("Denied")

        @requested.to(accepted, denied)
        def validate(self):
            return 1, 2

    machine = ApprovalMachine()

    assert machine.validate() == (
        1,
        2,
    )


@pytest.mark.parametrize(
    "payment_failed, expected_state",
    [
        (False, "paid"),
        (True, "failed"),
    ],
)
def test_multiple_destinations_using_or_starting_from_same_origin(
    payment_failed, expected_state
):
    class InvoiceStateMachine(StateMachine):
        unpaid = State("unpaid", initial=True)
        paid = State("paid")
        failed = State("failed")

        pay = (
            unpaid.to(paid, unless="payment_success")
            | failed.to(paid)
            | unpaid.to(failed)
        )

        def payment_success(self, event_data):
            return payment_failed

    invoice_fsm = InvoiceStateMachine()
    invoice_fsm.pay()
    assert invoice_fsm.current_state.identifier == expected_state


def test_order_control(OrderControl):
    control = OrderControl()
    assert control.add_to_order(3) == 3
    assert control.add_to_order(7) == 10

    control.receive_payment(4)
    with pytest.raises(exceptions.TransitionNotAllowed):
        control.process_order()

    control.receive_payment(6)
    control.process_order()

    control.ship_order()
    assert control.order_total == 10
    assert control.payments == [4, 6]
    assert control.is_completed
