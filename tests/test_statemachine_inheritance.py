# coding: utf-8

import pytest

from statemachine import exceptions


@pytest.fixture
def BaseMachine():
    from statemachine import StateMachine, State

    class BaseMachine(StateMachine):
        state_1 = State('1', initial=True)
        state_2 = State('2')
        trans_1_2 = state_1.to(state_2)

    return BaseMachine


@pytest.fixture
def InheritedClass(BaseMachine):
    class InheritedClass(BaseMachine):
        pass

    return InheritedClass


@pytest.fixture
def ExtendedClass(BaseMachine):
    from statemachine import State

    class ExtendedClass(BaseMachine):
        state_3 = State('3')
        trans_2_3 = BaseMachine.state_2.to(state_3)

    return ExtendedClass


@pytest.fixture
def OverridedClass(BaseMachine):
    from statemachine import State

    class OverridedClass(BaseMachine):
        state_2 = State('2', value='state_2')

    return OverridedClass


@pytest.fixture
def OverridedTransitionClass(BaseMachine):
    from statemachine import State

    class OverridedTransitionClass(BaseMachine):
        state_3 = State('3')
        trans_1_2 = BaseMachine.state_1.to(state_3)

    return OverridedTransitionClass


def test_should_inherit_states_and_transitions(BaseMachine, InheritedClass):
    assert InheritedClass.states == [
        BaseMachine.state_1,
        BaseMachine.state_2,
    ]
    assert InheritedClass.transitions == [
        BaseMachine.trans_1_2.target,
    ]


def test_should_extend_states_and_transitions(BaseMachine, ExtendedClass):
    assert ExtendedClass.states == [
        BaseMachine.state_1,
        BaseMachine.state_2,
        ExtendedClass.state_3,
    ]
    assert ExtendedClass.transitions == [
        BaseMachine.trans_1_2.target,
        ExtendedClass.trans_2_3.target,
    ]


def test_should_execute_transitions(ExtendedClass):
    instance = ExtendedClass()
    instance.trans_1_2()
    instance.trans_2_3()

    assert instance.is_state_3


def test_dont_support_overriden_states(OverridedClass):
    # There's no support for overriding states
    with pytest.raises(exceptions.InvalidDefinition):
        OverridedClass()


def test_support_override_transitions(OverridedTransitionClass):
    instance = OverridedTransitionClass()

    instance.trans_1_2()
    assert instance.is_state_3
