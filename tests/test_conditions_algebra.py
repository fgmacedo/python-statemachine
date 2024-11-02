import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.exceptions import InvalidDefinition


class AnyConditionSM(StateMachine):
    start = State(initial=True)
    end = State(final=True)

    submit = start.to(end, cond="used_money or used_credit")

    used_money: bool = False
    used_credit: bool = False


def test_conditions_algebra_any_false():
    sm = AnyConditionSM()
    with pytest.raises(sm.TransitionNotAllowed):
        sm.submit()

    assert sm.current_state == sm.start


def test_conditions_algebra_any_left_true():
    sm = AnyConditionSM()
    sm.used_money = True
    sm.submit()
    assert sm.current_state == sm.end


def test_conditions_algebra_any_right_true():
    sm = AnyConditionSM()
    sm.used_credit = True
    sm.submit()
    assert sm.current_state == sm.end


def test_should_raise_invalid_definition_if_cond_is_not_valid_sintax():
    class AnyConditionSM(StateMachine):
        start = State(initial=True)
        end = State(final=True)

        submit = start.to(end, cond="used_money xxx")

        used_money: bool = False
        used_credit: bool = False

    with pytest.raises(InvalidDefinition, match="Failed to parse boolean expression"):
        AnyConditionSM()


def test_should_raise_invalid_definition_if_cond_is_not_found():
    class AnyConditionSM(StateMachine):
        start = State(initial=True)
        end = State(final=True)

        submit = start.to(end, cond="used_money and xxx")

        used_money: bool = False
        used_credit: bool = False

    with pytest.raises(InvalidDefinition, match="Did not found name 'xxx'"):
        AnyConditionSM()
