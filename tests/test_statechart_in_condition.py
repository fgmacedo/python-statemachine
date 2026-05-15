"""In('state_id') condition for cross-state checks.

Tests exercise In() conditions that enable/block transitions based on whether
a given state is active, cross-region In() in parallel states, In() with
compound descendants, combined event + In() guards, and eventless + In() guards.

Theme: Fellowship coordination — actions depend on where members are.
"""

import pytest

from tests.machines.in_condition.combined_guard import CombinedGuard
from tests.machines.in_condition.descendant_check import DescendantCheck
from tests.machines.in_condition.eventless_in import EventlessIn
from tests.machines.in_condition.fellowship import Fellowship
from tests.machines.in_condition.fellowship_coordination import FellowshipCoordination
from tests.machines.in_condition.gate_of_moria import GateOfMoria


@pytest.mark.timeout(5)
class TestInCondition:
    async def test_in_condition_true_enables_transition(self, sm_runner):
        """In('state_id') when state is active -> transition fires."""
        sm = await sm_runner.start(Fellowship)
        await sm_runner.send(sm, "journey")
        vals = set(sm.configuration_values)
        assert "mordor_f" in vals
        assert "mordor_s" in vals

    async def test_in_condition_false_blocks_transition(self, sm_runner):
        """In('state_id') when state is not active -> transition blocked."""
        sm = await sm_runner.start(GateOfMoria)
        await sm_runner.send(sm, "enter_gate")
        assert "outside" in sm.configuration_values

    async def test_in_with_parallel_regions(self, sm_runner):
        """Cross-region In() evaluation in parallel states."""
        sm = await sm_runner.start(FellowshipCoordination)
        vals = set(sm.configuration_values)
        assert "waiting" in vals
        assert "scouting" in vals

        await sm_runner.send(sm, "report")
        vals = set(sm.configuration_values)
        assert "reported" in vals
        assert "marching" in vals

    async def test_in_with_compound_descendant(self, sm_runner):
        """In('child') when child is an active descendant."""
        sm = await sm_runner.start(DescendantCheck)
        await sm_runner.send(sm, "conquer")
        assert "realm" in sm.configuration_values

        await sm_runner.send(sm, "ascend")
        assert "castle" in sm.configuration_values

        await sm_runner.send(sm, "conquer")
        assert {"conquered"} == set(sm.configuration_values)

    async def test_in_combined_with_event(self, sm_runner):
        """Event + In() guard together."""
        sm = await sm_runner.start(CombinedGuard)
        await sm_runner.send(sm, "charge")
        assert "idle" in sm.configuration_values

        await sm_runner.send(sm, "return_scout")
        await sm_runner.send(sm, "charge")
        assert "attacking" in sm.configuration_values

    async def test_in_with_eventless_transition(self, sm_runner):
        """Eventless + In() guard."""
        sm = await sm_runner.start(EventlessIn)
        assert "waiting" in sm.configuration_values

        await sm_runner.send(sm, "get_ready")
        vals = set(sm.configuration_values)
        assert "ready" in vals
        assert "moving" in vals
