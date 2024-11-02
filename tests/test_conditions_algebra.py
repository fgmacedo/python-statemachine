import pytest

from statemachine import State
from statemachine import StateMachine


class AnyConditionSM(StateMachine):
    # write an example of StateMachine that transition if any of the two conditions is True
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
