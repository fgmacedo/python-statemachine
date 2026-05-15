"""Eventless (automatic) transitions with guards.

Tests exercise eventless transitions that fire when conditions are met,
stay inactive when conditions are false, cascade through chains in a single
macrostep, work with gradual threshold conditions, and combine with In() guards.

Theme: The One Ring's corruption and Beacons of Gondor.
"""

import pytest

from tests.machines.eventless.auto_advance import AutoAdvance
from tests.machines.eventless.beacon_chain import BeaconChain
from tests.machines.eventless.beacon_chain_lighting import BeaconChainLighting
from tests.machines.eventless.coordinated_advance import CoordinatedAdvance
from tests.machines.eventless.ring_corruption import RingCorruption
from tests.machines.eventless.ring_corruption_with_bear_ring import RingCorruptionWithBearRing
from tests.machines.eventless.ring_corruption_with_tick import RingCorruptionWithTick


@pytest.mark.timeout(5)
class TestEventlessTransitions:
    async def test_eventless_fires_when_condition_met(self, sm_runner):
        """Eventless transition fires when guard is True."""
        sm = await sm_runner.start(RingCorruption)
        assert "resisting" in sm.configuration_values

        sm.ring_power = 6
        # Need to trigger processing loop — send a no-op event
        await sm_runner.send(sm, "tick")
        assert "corrupted" in sm.configuration_values

    async def test_eventless_does_not_fire_when_condition_false(self, sm_runner):
        """Eventless transition stays when guard is False."""
        sm = await sm_runner.start(RingCorruptionWithTick)
        sm.ring_power = 2
        await sm_runner.send(sm, "tick")
        assert "resisting" in sm.configuration_values

    async def test_eventless_chain_cascades(self, sm_runner):
        """All beacons light in a single macrostep via unconditional eventless chain."""
        sm = await sm_runner.start(BeaconChainLighting)
        # The chain should cascade through all states in a single macrostep
        assert {"all_lit"} == set(sm.configuration_values)

    async def test_eventless_gradual_condition(self, sm_runner):
        """Multiple events needed before the condition threshold is met."""
        sm = await sm_runner.start(RingCorruptionWithBearRing)
        await sm_runner.send(sm, "bear_ring")  # power = 2
        assert "resisting" in sm.configuration_values

        await sm_runner.send(sm, "bear_ring")  # power = 4
        assert "resisting" in sm.configuration_values

        await sm_runner.send(sm, "bear_ring")  # power = 6 -> threshold exceeded
        assert "corrupted" in sm.configuration_values

    async def test_eventless_in_compound_state(self, sm_runner):
        """Eventless transition between compound children."""
        sm = await sm_runner.start(AutoAdvance)
        # Eventless chain cascades through all children
        assert {"done"} == set(sm.configuration_values)

    async def test_eventless_with_in_condition(self, sm_runner):
        """Eventless transition guarded by In('state_id')."""
        sm = await sm_runner.start(CoordinatedAdvance)
        assert "waiting" in sm.configuration_values

        await sm_runner.send(sm, "move_forward")
        # Vanguard advances, then rearguard's eventless fires
        vals = set(sm.configuration_values)
        assert "advanced" in vals
        assert "moved_up" in vals

    async def test_eventless_chain_with_final_triggers_done(self, sm_runner):
        """Eventless chain reaches final state -> done.state fires."""
        sm = await sm_runner.start(BeaconChain)
        assert {"signal_received"} == set(sm.configuration_values)
