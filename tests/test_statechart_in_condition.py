"""In('state_id') condition for cross-state checks.

Tests exercise In() conditions that enable/block transitions based on whether
a given state is active, cross-region In() in parallel states, In() with
compound descendants, combined event + In() guards, and eventless + In() guards.

Theme: Fellowship coordination — actions depend on where members are.
"""

import pytest

from statemachine import State
from statemachine import StateChart


@pytest.mark.timeout(5)
class TestInCondition:
    async def test_in_condition_true_enables_transition(self, sm_runner):
        """In('state_id') when state is active -> transition fires."""

        class Fellowship(StateChart):
            validate_disconnected_states = False

            class positions(State.Parallel):
                class frodo(State.Compound):
                    shire_f = State(initial=True)
                    mordor_f = State(final=True)

                    journey = shire_f.to(mordor_f)

                class sam(State.Compound):
                    shire_s = State(initial=True)
                    mordor_s = State(final=True)

                    # Sam follows Frodo: eventless, guarded by In('mordor_f')
                    shire_s.to(mordor_s, cond="In('mordor_f')")

        sm = await sm_runner.start(Fellowship)
        await sm_runner.send(sm, "journey")
        vals = set(sm.configuration_values)
        assert "mordor_f" in vals
        assert "mordor_s" in vals

    async def test_in_condition_false_blocks_transition(self, sm_runner):
        """In('state_id') when state is not active -> transition blocked."""

        class GateOfMoria(StateChart):
            outside = State(initial=True)
            at_gate = State()
            inside = State(final=True)

            approach = outside.to(at_gate)
            # Can only enter if we are at the gate
            enter_gate = outside.to(inside, cond="In('at_gate')")
            speak_friend = at_gate.to(inside)

        sm = await sm_runner.start(GateOfMoria)
        await sm_runner.send(sm, "enter_gate")
        assert "outside" in sm.configuration_values

    async def test_in_with_parallel_regions(self, sm_runner):
        """Cross-region In() evaluation in parallel states."""

        class FellowshipCoordination(StateChart):
            validate_disconnected_states = False

            class mission(State.Parallel):
                class scouts(State.Compound):
                    scouting = State(initial=True)
                    reported = State(final=True)

                    report = scouting.to(reported)

                class army(State.Compound):
                    waiting = State(initial=True)
                    marching = State(final=True)

                    # Army marches only after scouts report
                    waiting.to(marching, cond="In('reported')")

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

        class DescendantCheck(StateChart):
            class realm(State.Compound):
                village = State(initial=True)
                castle = State()

                ascend = village.to(castle)

            conquered = State(final=True)
            # Guarded by being inside the castle
            conquer = realm.to(conquered, cond="In('castle')")
            explore = realm.to.itself(internal=True)

        sm = await sm_runner.start(DescendantCheck)
        await sm_runner.send(sm, "conquer")
        assert "realm" in sm.configuration_values

        await sm_runner.send(sm, "ascend")
        assert "castle" in sm.configuration_values

        await sm_runner.send(sm, "conquer")
        assert {"conquered"} == set(sm.configuration_values)

    async def test_in_combined_with_event(self, sm_runner):
        """Event + In() guard together."""

        class CombinedGuard(StateChart):
            validate_disconnected_states = False

            class positions(State.Parallel):
                class scout(State.Compound):
                    out = State(initial=True)
                    back = State(final=True)

                    return_scout = out.to(back)

                class warrior(State.Compound):
                    idle = State(initial=True)
                    attacking = State(final=True)

                    # Only attacks when scout is back
                    charge = idle.to(attacking, cond="In('back')")

        sm = await sm_runner.start(CombinedGuard)
        await sm_runner.send(sm, "charge")
        assert "idle" in sm.configuration_values

        await sm_runner.send(sm, "return_scout")
        await sm_runner.send(sm, "charge")
        assert "attacking" in sm.configuration_values

    async def test_in_with_eventless_transition(self, sm_runner):
        """Eventless + In() guard."""

        class EventlessIn(StateChart):
            validate_disconnected_states = False

            class coordination(State.Parallel):
                class leader(State.Compound):
                    planning = State(initial=True)
                    ready = State(final=True)

                    get_ready = planning.to(ready)

                class follower(State.Compound):
                    waiting = State(initial=True)
                    moving = State(final=True)

                    # Eventless: move when leader is ready
                    waiting.to(moving, cond="In('ready')")

        sm = await sm_runner.start(EventlessIn)
        assert "waiting" in sm.configuration_values

        await sm_runner.send(sm, "get_ready")
        vals = set(sm.configuration_values)
        assert "ready" in vals
        assert "moving" in vals
