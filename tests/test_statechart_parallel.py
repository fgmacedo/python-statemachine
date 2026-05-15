"""Parallel state behavior with independent regions.

Tests exercise entering parallel states (all regions activate), region isolation
(events in one region don't affect others), exiting parallel states, done.state
when all regions reach final, and mixed compound/parallel hierarchies.

Theme: War of the Ring — multiple simultaneous fronts.
"""

from enum import Enum
from enum import auto

import pytest
from statemachine.states import States

from statemachine import State
from statemachine import StateChart
from tests.machines.parallel.session import Session
from tests.machines.parallel.session_with_done_state import SessionWithDoneState
from tests.machines.parallel.two_towers import TwoTowers
from tests.machines.parallel.war_of_the_ring import WarOfTheRing
from tests.machines.parallel.war_with_exit import WarWithExit


@pytest.mark.timeout(5)
class TestParallelStates:
    async def test_parallel_activates_all_regions(self, sm_runner):
        """Entering a parallel state activates the initial child of every region."""
        sm = await sm_runner.start(WarOfTheRing)
        vals = set(sm.configuration_values)
        assert "war" in vals
        assert "frodos_quest" in vals
        assert "shire" in vals
        assert "aragorns_path" in vals
        assert "ranger" in vals
        assert "gandalfs_defense" in vals
        assert "rohan" in vals

    async def test_independent_transitions_in_regions(self, sm_runner):
        """An event in one region does not affect others."""
        sm = await sm_runner.start(WarOfTheRing)
        await sm_runner.send(sm, "journey")
        vals = set(sm.configuration_values)
        assert "mordor" in vals
        assert "ranger" in vals  # unchanged
        assert "rohan" in vals  # unchanged

    async def test_configuration_includes_all_active_states(self, sm_runner):
        """Configuration set includes all active states across regions."""
        sm = await sm_runner.start(WarOfTheRing)
        config_ids = {s.id for s in sm.configuration}
        assert config_ids == {
            "war",
            "frodos_quest",
            "shire",
            "aragorns_path",
            "ranger",
            "gandalfs_defense",
            "rohan",
        }

    async def test_exit_parallel_exits_all_regions(self, sm_runner):
        """Transition out of a parallel clears everything."""
        sm = await sm_runner.start(WarWithExit)
        assert "war" in sm.configuration_values
        await sm_runner.send(sm, "truce")
        assert {"peace"} == set(sm.configuration_values)

    async def test_event_in_one_region_no_effect_on_others(self, sm_runner):
        """Region isolation: events affect only the targeted region."""
        sm = await sm_runner.start(WarOfTheRing)
        await sm_runner.send(sm, "coronation")
        vals = set(sm.configuration_values)
        assert "king" in vals
        assert "shire" in vals  # Frodo's region unchanged
        assert "rohan" in vals  # Gandalf's region unchanged

    async def test_parallel_with_compound_children(self, sm_runner):
        """Mixed hierarchy: parallel with compound regions verified."""
        sm = await sm_runner.start(WarOfTheRing)
        assert "shire" in sm.configuration_values
        assert "ranger" in sm.configuration_values
        assert "rohan" in sm.configuration_values

    async def test_current_state_value_set_comparison(self, sm_runner):
        """configuration_values supports set comparison for parallel states."""
        sm = await sm_runner.start(WarOfTheRing)
        vals = set(sm.configuration_values)
        expected = {
            "war",
            "frodos_quest",
            "shire",
            "aragorns_path",
            "ranger",
            "gandalfs_defense",
            "rohan",
        }
        assert vals == expected

    async def test_parallel_done_when_all_regions_final(self, sm_runner):
        """done.state fires when ALL regions reach a final state."""
        sm = await sm_runner.start(TwoTowers)
        await sm_runner.send(sm, "win")
        # Only one region is final, battle continues
        assert "battle" in sm.configuration_values

        await sm_runner.send(sm, "flood")
        # Both regions are final -> done.state.battle fires
        assert {"aftermath"} == set(sm.configuration_values)

    async def test_parallel_not_done_when_one_region_final(self, sm_runner):
        """Parallel not done when only one region reaches final."""
        sm = await sm_runner.start(TwoTowers)
        await sm_runner.send(sm, "win")
        assert "battle" in sm.configuration_values
        assert "victory" in sm.configuration_values
        assert "besieging" in sm.configuration_values

    async def test_transition_within_compound_inside_parallel(self, sm_runner):
        """Deep transition within a compound region of a parallel state."""
        sm = await sm_runner.start(WarOfTheRing)
        await sm_runner.send(sm, "journey")
        await sm_runner.send(sm, "destroy_ring")
        vals = set(sm.configuration_values)
        assert "mount_doom" in vals
        assert "ranger" in vals  # other regions unchanged

    async def test_top_level_parallel_terminates_when_all_children_final(self, sm_runner):
        """A root parallel terminates when all regions reach final states."""
        sm = await sm_runner.start(Session)
        assert sm.is_terminated is False

        await sm_runner.send(sm, "close_ui")
        assert sm.is_terminated is False  # one region still active

        await sm_runner.send(sm, "stop_backend")
        assert sm.is_terminated is True

    async def test_top_level_parallel_done_state_fires_before_termination(self, sm_runner):
        """done.state fires and transitions before root-final check terminates."""
        sm = await sm_runner.start(SessionWithDoneState)
        await sm_runner.send(sm, "close_ui")
        await sm_runner.send(sm, "stop_backend")
        # done.state.session fires, transitions to finished, then terminates
        assert {"finished"} == set(sm.configuration_values)
        assert sm.is_terminated is True

    async def test_from_enum_inside_parallel(self, sm_runner):
        """States.from_enum() works inside parallel states (#606)."""

        class RegionA(Enum):
            IDLE = auto()
            ACTIVE = auto()

        class RegionB(Enum):
            OFF = auto()
            ON = auto()

        class SC(StateChart):
            start = State(initial=True)
            done = State(final=True)

            class work(State.Parallel):
                class region_a(State.Compound):
                    a = States.from_enum(RegionA, initial=RegionA.IDLE, final=RegionA.ACTIVE)
                    go_a = a.IDLE.to(a.ACTIVE)

                class region_b(State.Compound):
                    b = States.from_enum(RegionB, initial=RegionB.OFF, final=RegionB.ON)
                    go_b = b.OFF.to(b.ON)

            begin = start.to(work)
            finish = work.to(done)

        sm = await sm_runner.start(SC)
        assert {"start"} == set(sm.configuration_values)

        await sm_runner.send(sm, "begin")
        vals = set(sm.configuration_values)
        assert "work" in vals
        assert RegionA.IDLE in vals
        assert RegionB.OFF in vals

        await sm_runner.send(sm, "go_a")
        vals = set(sm.configuration_values)
        assert RegionA.ACTIVE in vals
        assert RegionB.OFF in vals  # region_b unchanged

        await sm_runner.send(sm, "go_b")
        # Both regions final -> done.state.work fires
        assert {RegionA.ACTIVE, RegionB.ON} <= set(sm.configuration_values) or {"done"} == set(
            sm.configuration_values
        )

    async def test_top_level_parallel_not_terminated_when_one_region_pending(self, sm_runner):
        """Machine keeps running when only one region reaches final."""
        sm = await sm_runner.start(Session)
        await sm_runner.send(sm, "close_ui")
        assert sm.is_terminated is False
        assert "closed" in sm.configuration_values
        assert "running" in sm.configuration_values
