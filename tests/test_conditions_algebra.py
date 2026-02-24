import pytest
from statemachine.exceptions import InvalidDefinition

from statemachine import State
from statemachine import StateChart


class AnyConditionSM(StateChart):
    allow_event_without_transition = False
    catch_errors_as_events = False

    start = State(initial=True)
    end = State(final=True)

    submit = start.to(end, cond="used_money or used_credit")

    used_money: bool = False
    used_credit: bool = False


def test_conditions_algebra_any_false():
    sm = AnyConditionSM()
    with pytest.raises(sm.TransitionNotAllowed):
        sm.submit()

    assert sm.start.is_active


def test_conditions_algebra_any_left_true():
    sm = AnyConditionSM()
    sm.used_money = True
    sm.submit()
    assert sm.end.is_active


def test_conditions_algebra_any_right_true():
    sm = AnyConditionSM()
    sm.used_credit = True
    sm.submit()
    assert sm.end.is_active


def test_should_raise_invalid_definition_if_cond_is_not_valid_sintax():
    class AnyConditionSM(StateChart):
        start = State(initial=True)
        end = State(final=True)

        submit = start.to(end, cond="used_money xxx")

        used_money: bool = False
        used_credit: bool = False

    with pytest.raises(InvalidDefinition, match="Failed to parse boolean expression"):
        AnyConditionSM()


def test_should_raise_invalid_definition_if_cond_is_not_found():
    class AnyConditionSM(StateChart):
        start = State(initial=True)
        end = State(final=True)

        submit = start.to(end, cond="used_money and xxx")

        used_money: bool = False
        used_credit: bool = False

    with pytest.raises(InvalidDefinition, match="Did not found name 'xxx'"):
        AnyConditionSM()
