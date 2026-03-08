"""Tests for the Configuration class internals.

These tests cover branches in statemachine/configuration.py that are not
exercised by the higher-level state machine tests.
"""

import warnings

from statemachine.orderedset import OrderedSet

from statemachine import State
from statemachine import StateChart


class ParallelSM(StateChart):
    """A parallel state chart for testing multi-element configuration."""

    s1 = State(initial=True)
    s2 = State()
    s3 = State(final=True)

    go = s1.to(s2)
    finish = s2.to(s3)


class TestConfigurationStatesSetter:
    def test_set_empty_configuration(self):
        sm = ParallelSM()
        assert len(sm.configuration) > 0

        sm.configuration = OrderedSet()
        assert sm.current_state_value is None

    def test_set_multi_element_configuration(self):
        sm = ParallelSM()
        s1_inst = sm.s1
        s2_inst = sm.s2

        sm.configuration = OrderedSet([s1_inst, s2_inst])
        assert isinstance(sm.current_state_value, OrderedSet)
        assert sm.current_state_value == OrderedSet([ParallelSM.s1.value, ParallelSM.s2.value])


class TestConfigurationDiscard:
    def test_discard_nonmatching_scalar(self):
        sm = ParallelSM()
        # current value is s1 (scalar)
        assert sm.current_state_value == ParallelSM.s1.value

        # discard s2 — should be a no-op since s2 is not active
        sm._config.discard(ParallelSM.s2)
        assert sm.current_state_value == ParallelSM.s1.value


class TestConfigurationCurrentState:
    def test_current_state_with_multiple_active_states(self):
        sm = ParallelSM()
        s1_inst = sm.s1
        s2_inst = sm.s2
        sm.configuration = OrderedSet([s1_inst, s2_inst])

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = sm.current_state
        assert isinstance(result, OrderedSet)
        assert len(result) == 2
