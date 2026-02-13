"""Eventless (automatic) transitions with guards.

Tests exercise eventless transitions that fire when conditions are met,
stay inactive when conditions are false, cascade through chains in a single
macrostep, work with gradual threshold conditions, and combine with In() guards.

Theme: The One Ring's corruption and Beacons of Gondor.
"""

import pytest

from statemachine import State
from statemachine import StateChart


@pytest.mark.timeout(5)
class TestEventlessTransitions:
    async def test_eventless_fires_when_condition_met(self, sm_runner):
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

        sm = await sm_runner.start(RingCorruption)
        assert "resisting" in sm.configuration_values

        sm.ring_power = 6
        # Need to trigger processing loop — send a no-op event
        await sm_runner.send(sm, "tick")
        assert "corrupted" in sm.configuration_values

    async def test_eventless_does_not_fire_when_condition_false(self, sm_runner):
        """Eventless transition stays when guard is False."""

        class RingCorruption(StateChart):
            resisting = State(initial=True)
            corrupted = State(final=True)

            resisting.to(corrupted, cond="is_corrupted")
            tick = resisting.to.itself(internal=True)

            ring_power = 0

            def is_corrupted(self):
                return self.ring_power > 5

        sm = await sm_runner.start(RingCorruption)
        sm.ring_power = 2
        await sm_runner.send(sm, "tick")
        assert "resisting" in sm.configuration_values

    async def test_eventless_chain_cascades(self, sm_runner):
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
            done_state_chain = chain.to(all_lit)

        sm = await sm_runner.start(BeaconChainLighting)
        # The chain should cascade through all states in a single macrostep
        assert {"all_lit"} == set(sm.configuration_values)

    async def test_eventless_gradual_condition(self, sm_runner):
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

        sm = await sm_runner.start(RingCorruption)
        await sm_runner.send(sm, "bear_ring")  # power = 2
        assert "resisting" in sm.configuration_values

        await sm_runner.send(sm, "bear_ring")  # power = 4
        assert "resisting" in sm.configuration_values

        await sm_runner.send(sm, "bear_ring")  # power = 6 -> threshold exceeded
        assert "corrupted" in sm.configuration_values

    async def test_eventless_in_compound_state(self, sm_runner):
        """Eventless transition between compound children."""

        class AutoAdvance(StateChart):
            class journey(State.Compound):
                step1 = State(initial=True)
                step2 = State()
                step3 = State(final=True)

                step1.to(step2)
                step2.to(step3)

            done = State(final=True)
            done_state_journey = journey.to(done)

        sm = await sm_runner.start(AutoAdvance)
        # Eventless chain cascades through all children
        assert {"done"} == set(sm.configuration_values)

    async def test_eventless_with_in_condition(self, sm_runner):
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

        sm = await sm_runner.start(CoordinatedAdvance)
        assert "waiting" in sm.configuration_values

        await sm_runner.send(sm, "move_forward")
        # Vanguard advances, then rearguard's eventless fires
        vals = set(sm.configuration_values)
        assert "advanced" in vals
        assert "moved_up" in vals

    async def test_eventless_chain_with_final_triggers_done(self, sm_runner):
        """Eventless chain reaches final state -> done.state fires."""

        class BeaconChain(StateChart):
            class beacons(State.Compound):
                first = State(initial=True)
                last = State(final=True)

                first.to(last)

            signal_received = State(final=True)
            done_state_beacons = beacons.to(signal_received)

        sm = await sm_runner.start(BeaconChain)
        assert {"signal_received"} == set(sm.configuration_values)
