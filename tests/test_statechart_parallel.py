"""Parallel state behavior with independent regions.

Tests exercise entering parallel states (all regions activate), region isolation
(events in one region don't affect others), exiting parallel states, done.state
when all regions reach final, and mixed compound/parallel hierarchies.

Theme: War of the Ring — multiple simultaneous fronts.
"""

import pytest

from statemachine import Event
from statemachine import State
from statemachine import StateChart


@pytest.mark.timeout(5)
class TestParallelStates:
    @pytest.fixture()
    def war_of_the_ring_cls(self):
        class WarOfTheRing(StateChart):
            validate_disconnected_states = False

            class war(State.Parallel):
                class frodos_quest(State.Compound):
                    shire = State(initial=True)
                    mordor = State()
                    mount_doom = State(final=True)

                    journey = shire.to(mordor)
                    destroy_ring = mordor.to(mount_doom)

                class aragorns_path(State.Compound):
                    ranger = State(initial=True)
                    king = State(final=True)

                    coronation = ranger.to(king)

                class gandalfs_defense(State.Compound):
                    rohan = State(initial=True)
                    gondor = State(final=True)

                    ride_to_gondor = rohan.to(gondor)

        return WarOfTheRing

    def test_parallel_activates_all_regions(self, war_of_the_ring_cls):
        """Entering a parallel state activates the initial child of every region."""
        sm = war_of_the_ring_cls()
        vals = set(sm.configuration_values)
        assert "war" in vals
        assert "frodos_quest" in vals
        assert "shire" in vals
        assert "aragorns_path" in vals
        assert "ranger" in vals
        assert "gandalfs_defense" in vals
        assert "rohan" in vals

    def test_independent_transitions_in_regions(self, war_of_the_ring_cls):
        """An event in one region does not affect others."""
        sm = war_of_the_ring_cls()
        sm.send("journey")
        vals = set(sm.configuration_values)
        assert "mordor" in vals
        assert "ranger" in vals  # unchanged
        assert "rohan" in vals  # unchanged

    def test_configuration_includes_all_active_states(self, war_of_the_ring_cls):
        """Configuration set includes all active states across regions."""
        sm = war_of_the_ring_cls()
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

    def test_exit_parallel_exits_all_regions(self):
        """Transition out of a parallel clears everything."""

        class WarWithExit(StateChart):
            validate_disconnected_states = False

            class war(State.Parallel):
                class front_a(State.Compound):
                    fighting = State(initial=True, final=True)

                class front_b(State.Compound):
                    holding = State(initial=True, final=True)

            peace = State(final=True)
            truce = war.to(peace)

        sm = WarWithExit()
        assert "war" in sm.configuration_values
        sm.send("truce")
        assert {"peace"} == set(sm.configuration_values)

    def test_event_in_one_region_no_effect_on_others(self, war_of_the_ring_cls):
        """Region isolation: events affect only the targeted region."""
        sm = war_of_the_ring_cls()
        sm.send("coronation")
        vals = set(sm.configuration_values)
        assert "king" in vals
        assert "shire" in vals  # Frodo's region unchanged
        assert "rohan" in vals  # Gandalf's region unchanged

    def test_parallel_with_compound_children(self, war_of_the_ring_cls):
        """Mixed hierarchy: parallel with compound regions verified."""
        sm = war_of_the_ring_cls()
        # Each region is compound with its own initial child
        assert "shire" in sm.configuration_values
        assert "ranger" in sm.configuration_values
        assert "rohan" in sm.configuration_values

    def test_current_state_value_set_comparison(self, war_of_the_ring_cls):
        """configuration_values supports set comparison for parallel states."""
        sm = war_of_the_ring_cls()
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

    def test_parallel_done_when_all_regions_final(self):
        """done.state fires when ALL regions reach a final state."""

        class TwoTowers(StateChart):
            validate_disconnected_states = False

            class battle(State.Parallel):
                class helms_deep(State.Compound):
                    fighting = State(initial=True)
                    victory = State(final=True)

                    win = fighting.to(victory)

                class isengard(State.Compound):
                    besieging = State(initial=True)
                    flooded = State(final=True)

                    flood = besieging.to(flooded)

            aftermath = State(final=True)
            done_state_battle = Event(battle.to(aftermath), id="done.state.battle")

        sm = TwoTowers()
        sm.send("win")
        # Only one region is final, battle continues
        assert "battle" in sm.configuration_values

        sm.send("flood")
        # Both regions are final -> done.state.battle fires
        assert {"aftermath"} == set(sm.configuration_values)

    def test_parallel_not_done_when_one_region_final(self):
        """Parallel not done when only one region reaches final."""

        class TwoTowers(StateChart):
            validate_disconnected_states = False

            class battle(State.Parallel):
                class helms_deep(State.Compound):
                    fighting = State(initial=True)
                    victory = State(final=True)

                    win = fighting.to(victory)

                class isengard(State.Compound):
                    besieging = State(initial=True)
                    flooded = State(final=True)

                    flood = besieging.to(flooded)

            aftermath = State(final=True)
            done_state_battle = Event(battle.to(aftermath), id="done.state.battle")

        sm = TwoTowers()
        sm.send("win")
        assert "battle" in sm.configuration_values
        assert "victory" in sm.configuration_values
        assert "besieging" in sm.configuration_values

    def test_transition_within_compound_inside_parallel(self, war_of_the_ring_cls):
        """Deep transition within a compound region of a parallel state."""
        sm = war_of_the_ring_cls()
        sm.send("journey")
        sm.send("destroy_ring")
        vals = set(sm.configuration_values)
        assert "mount_doom" in vals
        assert "ranger" in vals  # other regions unchanged
