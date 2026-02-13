"""Error handling in compound and parallel contexts.

Tests exercise error.execution firing when on_enter raises in a compound child,
error handling in parallel regions, and error.execution transitions that leave
a compound state entirely.
"""

import pytest

from statemachine import Event
from statemachine import State
from statemachine import StateChart


@pytest.mark.timeout(5)
class TestErrorExecutionStatechart:
    def test_error_in_compound_child_onentry(self):
        """Error in on_enter of compound child fires error.execution."""

        class CompoundError(StateChart):
            class realm(State.Compound):
                safe = State(initial=True)
                danger = State()

                enter_danger = safe.to(danger)

                def on_enter_danger(self):
                    raise RuntimeError("Balrog awakens!")

            error_state = State(final=True)
            error_execution = Event(realm.to(error_state), id="error.execution")

        sm = CompoundError()
        sm.send("enter_danger")
        assert {"error_state"} == set(sm.configuration_values)

    def test_error_in_parallel_region_isolation(self):
        """Error in one parallel region; error.execution handles the exit."""

        class ParallelError(StateChart):
            validate_disconnected_states = False

            class fronts(State.Parallel):
                class battle_a(State.Compound):
                    fighting = State(initial=True)
                    victory = State()

                    win = fighting.to(victory)

                    def on_enter_victory(self):
                        raise RuntimeError("Ambush!")

                class battle_b(State.Compound):
                    holding = State(initial=True)
                    won = State(final=True)

                    triumph = holding.to(won)

            error_state = State(final=True)
            error_execution = Event(fronts.to(error_state), id="error.execution")

        sm = ParallelError()
        # Error in battle_a's on_enter_victory
        sm.send("win")
        # Error is raised, error.execution fires from fronts -> error_state
        assert {"error_state"} == set(sm.configuration_values)

    def test_error_recovery_exits_compound(self):
        """error.execution transition leaves compound state entirely."""

        class CompoundRecovery(StateChart):
            class dungeon(State.Compound):
                room_a = State(initial=True)
                room_b = State()

                explore = room_a.to(room_b)

                def on_enter_room_b(self):
                    raise RuntimeError("Trap!")

            safe = State(final=True)
            error_execution = Event(dungeon.to(safe), id="error.execution")

        sm = CompoundRecovery()
        sm.send("explore")
        assert {"safe"} == set(sm.configuration_values)
        assert "dungeon" not in sm.configuration_values
