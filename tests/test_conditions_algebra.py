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


def test_should_raise_invalid_definition_if_cond_has_unsupported_structure():
    class AnyConditionSM(StateChart):
        start = State(initial=True)
        end = State(final=True)

        submit = start.to(end, cond="user.age")

    with pytest.raises(InvalidDefinition, match="Failed to parse boolean expression 'user.age'"):
        AnyConditionSM()


def test_should_not_mask_errors_raised_while_resolving_names():
    # Resolving a name reads attributes from the model, which runs user code. An
    # error raised there is not a parse error and must not be reported as one.
    class Model:
        @property
        def is_ready(self):
            raise ValueError("the model is not configured")

    class AnyConditionSM(StateChart):
        start = State(initial=True)
        end = State(final=True)

        submit = start.to(end, cond="is_ready")

    model = Model()
    with pytest.raises(ValueError, match="the model is not configured"):
        AnyConditionSM(model)
