"""Eventless (automatic) transitions with guards.

Tests exercise eventless transitions that fire when conditions are met,
stay inactive when conditions are false, cascade through chains in a single
macrostep, work with gradual threshold conditions, and combine with In() guards.

Theme: The One Ring's corruption and Beacons of Gondor.
"""

import pytest

from statemachine import Event
from statemachine import State
from statemachine import StateChart


@pytest.mark.timeout(5)
class TestEventlessTransitions:
    def test_eventless_fires_when_condition_met(self):
        """Eventless transition fires when guard is True."""

        class RingCorruption(StateChart):
            resisting = State(initial=True)
            corrupted = State(final=True)

            # eventless: no event name
            resisting.to(corrupted, cond="is_corrupted")

            ring_power = 0

            def is_corrupted(self):
                return self.ring_power > 5

            def increase_power(self):
                self.ring_power += 3

        sm = RingCorruption()
        assert "resisting" in sm.configuration_values

        sm.ring_power = 6
        # Need to trigger processing loop — send a no-op event
        sm.send("tick")
        assert "corrupted" in sm.configuration_values

    def test_eventless_does_not_fire_when_condition_false(self):
        """Eventless transition stays when guard is False."""

        class RingCorruption(StateChart):
            resisting = State(initial=True)
            corrupted = State(final=True)

            resisting.to(corrupted, cond="is_corrupted")
            tick = resisting.to.itself(internal=True)

            ring_power = 0

            def is_corrupted(self):
                return self.ring_power > 5

        sm = RingCorruption()
        sm.ring_power = 2
        sm.send("tick")
        assert "resisting" in sm.configuration_values

    def test_eventless_chain_cascades(self):
        """All beacons light in a single macrostep via unconditional eventless chain."""

        class BeaconChainLighting(StateChart):
            class chain(State.Compound):
                amon_din = State(initial=True)
                eilenach = State()
                nardol = State()
                halifirien = State(final=True)

                # Eventless chain: each fires immediately
                amon_din.to(eilenach)
                eilenach.to(nardol)
                nardol.to(halifirien)

            all_lit = State(final=True)
            done_state_chain = Event(chain.to(all_lit), id="done.state.chain")

        sm = BeaconChainLighting()
        # The chain should cascade through all states in a single macrostep
        assert {"all_lit"} == set(sm.configuration_values)

    def test_eventless_gradual_condition(self):
        """Multiple events needed before the condition threshold is met."""

        class RingCorruption(StateChart):
            resisting = State(initial=True)
            corrupted = State(final=True)

            resisting.to(corrupted, cond="is_corrupted")
            bear_ring = resisting.to.itself(internal=True, on="increase_power")

            ring_power = 0

            def is_corrupted(self):
                return self.ring_power > 5

            def increase_power(self):
                self.ring_power += 2

        sm = RingCorruption()
        sm.send("bear_ring")  # power = 2
        assert "resisting" in sm.configuration_values

        sm.send("bear_ring")  # power = 4
        assert "resisting" in sm.configuration_values

        sm.send("bear_ring")  # power = 6 -> threshold exceeded
        assert "corrupted" in sm.configuration_values

    def test_eventless_in_compound_state(self):
        """Eventless transition between compound children."""

        class AutoAdvance(StateChart):
            class journey(State.Compound):
                step1 = State(initial=True)
                step2 = State()
                step3 = State(final=True)

                step1.to(step2)
                step2.to(step3)

            done = State(final=True)
            done_state_journey = Event(journey.to(done), id="done.state.journey")

        sm = AutoAdvance()
        # Eventless chain cascades through all children
        assert {"done"} == set(sm.configuration_values)

    def test_eventless_with_in_condition(self):
        """Eventless transition guarded by In('state_id')."""

        class CoordinatedAdvance(StateChart):
            validate_disconnected_states = False

            class forces(State.Parallel):
                class vanguard(State.Compound):
                    waiting = State(initial=True)
                    advanced = State(final=True)

                    move_forward = waiting.to(advanced)

                class rearguard(State.Compound):
                    holding = State(initial=True)
                    moved_up = State(final=True)

                    # Eventless: advance only when vanguard has advanced
                    holding.to(moved_up, cond="In('advanced')")

        sm = CoordinatedAdvance()
        assert "waiting" in sm.configuration_values

        sm.send("move_forward")
        # Vanguard advances, then rearguard's eventless fires
        vals = set(sm.configuration_values)
        assert "advanced" in vals
        assert "moved_up" in vals

    def test_eventless_chain_with_final_triggers_done(self):
        """Eventless chain reaches final state -> done.state fires."""

        class BeaconChain(StateChart):
            class beacons(State.Compound):
                first = State(initial=True)
                last = State(final=True)

                first.to(last)

            signal_received = State(final=True)
            done_state_beacons = Event(beacons.to(signal_received), id="done.state.beacons")

        sm = BeaconChain()
        assert {"signal_received"} == set(sm.configuration_values)
