import pytest

from statemachine import State
from statemachine import StateMachine


@pytest.fixture()
def simple_sm_cls():
    class TestStateMachine(StateMachine):
        # States
        initial = State("Initial", initial=True)
        final = State("Final", final=True, enter="do_enter_final")

        finish = initial.to(final, cond="can_finish", on="do_finish")

        def __init__(self, name):
            self.name = name
            self.can_finish = False
            self.finalized = False
            super(TestStateMachine, self).__init__()

        def do_finish(self):
            return self.name, self.can_finish

        def do_enter_final(self):
            self.finalized = True

    return TestStateMachine


class TestCallbacksIsolation:
    def test_should_conditions_be_isolated(self, simple_sm_cls):
        sm1 = simple_sm_cls("sm1")
        sm2 = simple_sm_cls("sm2")
        sm3 = simple_sm_cls("sm3")

        sm1.can_finish = True
        assert sm1.initial.transitions[0].cond.call() == [True]
        assert sm2.initial.transitions[0].cond.call() == [False]
        assert sm3.initial.transitions[0].cond.call() == [False]

    def test_should_actions_be_isolated(self, simple_sm_cls):
        sm1 = simple_sm_cls("sm1")
        sm2 = simple_sm_cls("sm2")

        sm1.can_finish = True
        sm2.can_finish = True

        sm1_initial = sm1.initial
        sm1_final = sm1.final

        assert sm2.finish() == ("sm2", True)

        assert not sm2.initial.is_active
        assert sm2.final.is_active
        assert sm2.finalized is True

        assert sm1_initial.is_active
        assert not sm1_final.is_active
        assert sm1.finalized is False

        assert sm1.initial.is_active
        assert not sm1.final.is_active

        assert sm1.finish() == ("sm1", True)

        assert sm1.finalized is True
        assert not sm1.initial.is_active
        assert sm1.final.is_active

    def test_instance_states_and_transitions_are_isolated(self, simple_sm_cls):
        sm1 = simple_sm_cls("sm1")

        assert sm1.initial == simple_sm_cls.initial
        assert sm1.initial is not simple_sm_cls.initial

        assert repr(sm1.initial.transitions[0]) == repr(
            simple_sm_cls.initial.transitions[0]
        )
        assert sm1.initial.transitions[0] is not simple_sm_cls.initial.transitions[0]
