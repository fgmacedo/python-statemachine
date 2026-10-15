"""History state behavior with shallow and deep history.

Tests exercise shallow history (remembers last direct child), deep history
(remembers exact leaf in nested compounds), default transitions on first visit,
multiple exit/reentry cycles, and the history_values dict.

Theme: Gollum's dual personality — remembers which was active.
"""

import pytest

from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart
from tests.machines.history.deep_memory_of_moria import DeepMemoryOfMoria
from tests.machines.history.gollum_personality import GollumPersonality
from tests.machines.history.gollum_personality_default_gollum import GollumPersonalityDefaultGollum
from tests.machines.history.gollum_personality_with_default import GollumPersonalityWithDefault
from tests.machines.history.shallow_moria import ShallowMoria


@pytest.mark.timeout(5)
class TestHistoryStates:
    async def test_shallow_history_remembers_last_child(self, sm_runner):
        """Exit compound, re-enter via history -> restores last active child."""
        sm = await sm_runner.start(GollumPersonality)
        await sm_runner.send(sm, "dark_side")
        assert "gollum" in sm.configuration_values

        await sm_runner.send(sm, "leave")
        assert {"outside"} == set(sm.configuration_values)

        await sm_runner.send(sm, "return_via_history")
        assert "gollum" in sm.configuration_values
        assert "personality" in sm.configuration_values

    async def test_shallow_history_default_on_first_visit(self, sm_runner):
        """No prior visit -> history uses default transition target."""
        sm = await sm_runner.start(GollumPersonalityWithDefault)
        assert {"outside"} == set(sm.configuration_values)

        await sm_runner.send(sm, "enter_via_history")
        assert "smeagol" in sm.configuration_values

    async def test_deep_history_remembers_full_descendant(self, sm_runner):
        """Deep history restores the exact leaf in a nested compound."""
        sm = await sm_runner.start(DeepMemoryOfMoria)
        await sm_runner.send(sm, "explore")
        assert "chamber" in sm.configuration_values

        await sm_runner.send(sm, "escape")
        assert {"outside"} == set(sm.configuration_values)

        await sm_runner.send(sm, "return_deep")
        assert "chamber" in sm.configuration_values
        assert "halls" in sm.configuration_values
        assert "moria" in sm.configuration_values

    async def test_multiple_exits_and_reentries(self, sm_runner):
        """History updates each time we exit the compound."""
        sm = await sm_runner.start(GollumPersonality)
        await sm_runner.send(sm, "leave")
        await sm_runner.send(sm, "return_via_history")
        assert "smeagol" in sm.configuration_values

        await sm_runner.send(sm, "dark_side")
        await sm_runner.send(sm, "leave")
        await sm_runner.send(sm, "return_via_history")
        assert "gollum" in sm.configuration_values

        await sm_runner.send(sm, "light_side")
        await sm_runner.send(sm, "leave")
        await sm_runner.send(sm, "return_via_history")
        assert "smeagol" in sm.configuration_values

    async def test_history_after_state_change(self, sm_runner):
        """Change state within compound, exit, re-enter -> new state restored."""
        sm = await sm_runner.start(GollumPersonality)
        await sm_runner.send(sm, "dark_side")
        await sm_runner.send(sm, "leave")
        await sm_runner.send(sm, "return_via_history")
        assert "gollum" in sm.configuration_values

    async def test_shallow_only_remembers_immediate_child(self, sm_runner):
        """Shallow history in nested compound restores direct child, not grandchild."""
        sm = await sm_runner.start(ShallowMoria)
        await sm_runner.send(sm, "explore")
        assert "chamber" in sm.configuration_values

        await sm_runner.send(sm, "escape")
        await sm_runner.send(sm, "return_shallow")
        # Shallow history restores 'halls' as the direct child,
        # but re-enters halls at its initial state (entrance), not chamber
        assert "halls" in sm.configuration_values
        assert "entrance" in sm.configuration_values

    async def test_history_values_dict_populated(self, sm_runner):
        """sm.history_values[history_id] has saved states after exit."""
        sm = await sm_runner.start(GollumPersonality)
        await sm_runner.send(sm, "dark_side")
        await sm_runner.send(sm, "leave")
        assert "h" in sm.history_values
        saved = sm.history_values["h"]
        assert len(saved) == 1
        assert saved[0].id == "gollum"

    async def test_history_with_default_transition(self, sm_runner):
        """HistoryState with explicit default .to() transition."""
        sm = await sm_runner.start(GollumPersonalityDefaultGollum)
        await sm_runner.send(sm, "enter_via_history")
        assert "gollum" in sm.configuration_values


def _build_traced_machine(kind, with_default=False):
    class Traced(StateChart):
        outside = State(initial=True)

        class region(State.Compound):
            class nested(State.Compound):
                n1 = State(initial=True)
                n2 = State()
                deeper = n1.to(n2)

            other = State()
            h = HistoryState(type=kind)
            sideways = nested.to(other)
            if with_default:
                h.to(other, on="default_effect")

        enter = outside.to(region, on="enter_effect")
        leave = region.to(outside)
        back = outside.to(region.h, on="back_effect")

        def __init__(self, *args, **kwargs):
            self.trace = []
            super().__init__(*args, **kwargs)

        def enter_effect(self):
            self.trace.append("enter_effect")

        def back_effect(self):
            self.trace.append("back_effect")

        def default_effect(self):
            self.trace.append("default_effect")

        def on_enter_state(self, target):
            self.trace.append(f"enter:{target.id}")

        def on_exit_state(self, source):
            self.trace.append(f"exit:{source.id}")

    return Traced


@pytest.mark.timeout(5)
@pytest.mark.parametrize("kind", ["shallow", "deep"])
class TestHistoryDefaultEntry:
    async def test_no_stored_value_and_no_default_enters_parent_by_default(self, sm_runner, kind):
        sm = await sm_runner.start(_build_traced_machine(kind))
        sm.trace.clear()

        await sm_runner.send(sm, "back")

        assert {"region", "nested", "n1"} == set(sm.configuration_values)
        assert sm.trace == [
            "exit:outside",
            "back_effect",
            "enter:region",
            "enter:nested",
            "enter:n1",
        ]

    async def test_machine_keeps_running_after_default_entry_of_parent(self, sm_runner, kind):
        sm = await sm_runner.start(_build_traced_machine(kind))
        await sm_runner.send(sm, "back")
        await sm_runner.send(sm, "deeper")
        await sm_runner.send(sm, "leave")
        await sm_runner.send(sm, "back")

        expected_leaf = "n2" if kind == "deep" else "n1"
        assert {"region", "nested", expected_leaf} == set(sm.configuration_values)

    async def test_stored_value_runs_incoming_effect_once(self, sm_runner, kind):
        sm = await sm_runner.start(_build_traced_machine(kind))
        await sm_runner.send(sm, "enter")
        await sm_runner.send(sm, "sideways")
        await sm_runner.send(sm, "leave")
        sm.trace.clear()

        await sm_runner.send(sm, "back")

        assert {"region", "other"} == set(sm.configuration_values)
        assert sm.trace == ["exit:outside", "back_effect", "enter:region", "enter:other"]

    async def test_default_runs_incoming_effect_once_then_default_effect(self, sm_runner, kind):
        sm = await sm_runner.start(_build_traced_machine(kind, with_default=True))
        sm.trace.clear()

        await sm_runner.send(sm, "back")

        assert {"region", "other"} == set(sm.configuration_values)
        assert sm.trace == [
            "exit:outside",
            "back_effect",
            "enter:region",
            "default_effect",
            "enter:other",
        ]

    async def test_stored_value_skips_default_effect(self, sm_runner, kind):
        sm = await sm_runner.start(_build_traced_machine(kind, with_default=True))
        await sm_runner.send(sm, "enter")
        await sm_runner.send(sm, "deeper")
        await sm_runner.send(sm, "leave")
        sm.trace.clear()

        await sm_runner.send(sm, "back")

        expected_leaf = "n2" if kind == "deep" else "n1"
        assert {"region", "nested", expected_leaf} == set(sm.configuration_values)
        assert sm.trace == [
            "exit:outside",
            "back_effect",
            "enter:region",
            "enter:nested",
            f"enter:{expected_leaf}",
        ]

    async def test_default_entry_of_parent_enters_its_ancestors(self, sm_runner, kind):
        class Nested(StateChart):
            outside = State(initial=True)

            class top(State.Compound):
                class region(State.Compound):
                    r1 = State(initial=True)
                    h = HistoryState(type=kind)

                t1 = State(initial=True)

            back = outside.to(top.region.h)

        sm = await sm_runner.start(Nested)

        await sm_runner.send(sm, "back")

        assert {"top", "region", "r1"} == set(sm.configuration_values)

    async def test_default_entry_of_parent_from_a_sibling(self, sm_runner, kind):
        class Siblings(StateChart):
            class top(State.Compound):
                t1 = State(initial=True)

                class region(State.Compound):
                    r1 = State(initial=True)
                    h = HistoryState(type=kind)

                back = t1.to(region.h)

        sm = await sm_runner.start(Siblings)

        await sm_runner.send(sm, "back")

        assert {"top", "region", "r1"} == set(sm.configuration_values)
