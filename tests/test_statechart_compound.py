"""Compound state behavior using Python class syntax.

Tests exercise entering/exiting compound states, nested compounds, cross-compound
transitions, done.state events from final children, callback ordering, and discovery
of methods defined inside State.Compound class bodies.

Theme: Fellowship journey through Middle-earth.
"""

from enum import Enum
from enum import auto

import pytest
from statemachine.states import States

from statemachine import State
from statemachine import StateChart
from tests.machines.compound.middle_earth_journey import MiddleEarthJourney
from tests.machines.compound.middle_earth_journey_two_compounds import (
    MiddleEarthJourneyTwoCompounds,
)
from tests.machines.compound.middle_earth_journey_with_finals import MiddleEarthJourneyWithFinals
from tests.machines.compound.moria_expedition import MoriaExpedition
from tests.machines.compound.moria_expedition_with_escape import MoriaExpeditionWithEscape
from tests.machines.compound.quest_for_erebor import QuestForErebor
from tests.machines.compound.shire_to_rivendell import ShireToRivendell


@pytest.mark.timeout(5)
class TestCompoundStates:
    async def test_enter_compound_activates_initial_child(self, sm_runner):
        """Entering a compound activates both parent and the initial child."""
        sm = await sm_runner.start(ShireToRivendell)
        assert {"shire", "bag_end"} == set(sm.configuration_values)

    async def test_transition_within_compound(self, sm_runner):
        """Inner state changes while parent stays active."""
        sm = await sm_runner.start(ShireToRivendell)
        await sm_runner.send(sm, "visit_pub")
        assert "shire" in sm.configuration_values
        assert "green_dragon" in sm.configuration_values
        assert "bag_end" not in sm.configuration_values

    async def test_exit_compound_removes_all_descendants(self, sm_runner):
        """Leaving a compound removes the parent and all children."""
        sm = await sm_runner.start(ShireToRivendell)
        await sm_runner.send(sm, "depart")
        assert {"road"} == set(sm.configuration_values)

    async def test_nested_compound_two_levels(self, sm_runner):
        """Three-level nesting: outer > middle > leaf."""
        sm = await sm_runner.start(MoriaExpedition)
        assert {"moria", "upper_halls", "entrance"} == set(sm.configuration_values)

    async def test_transition_from_inner_to_outer(self, sm_runner):
        """A deep child can transition to an outer state."""
        sm = await sm_runner.start(MoriaExpeditionWithEscape)
        await sm_runner.send(sm, "escape")
        assert {"daylight"} == set(sm.configuration_values)

    async def test_cross_compound_transition(self, sm_runner):
        """Transition from one compound to another removes old children."""
        sm = await sm_runner.start(MiddleEarthJourney)
        assert "rivendell" in sm.configuration_values
        assert "council" in sm.configuration_values

        await sm_runner.send(sm, "march_to_moria")
        assert "moria" in sm.configuration_values
        assert "gates" in sm.configuration_values
        assert "rivendell" not in sm.configuration_values
        assert "council" not in sm.configuration_values

    async def test_enter_compound_lands_on_initial(self, sm_runner):
        """Entering a compound from outside lands on the initial child."""
        sm = await sm_runner.start(MiddleEarthJourneyTwoCompounds)
        await sm_runner.send(sm, "march_to_moria")
        assert "gates" in sm.configuration_values
        assert "moria" in sm.configuration_values

    async def test_final_child_fires_done_state(self, sm_runner):
        """Reaching a final child triggers done.state.{parent_id}."""
        sm = await sm_runner.start(QuestForErebor)
        assert "approach" in sm.configuration_values

        await sm_runner.send(sm, "enter_mountain")
        assert {"victory"} == set(sm.configuration_values)

    async def test_multiple_compound_sequential_traversal(self, sm_runner):
        """Traverse all three compounds sequentially."""
        sm = await sm_runner.start(MiddleEarthJourneyWithFinals)
        await sm_runner.send(sm, "march_to_moria")
        assert "moria" in sm.configuration_values

        await sm_runner.send(sm, "march_to_lorien")
        assert "lothlorien" in sm.configuration_values
        assert "mirror" in sm.configuration_values
        assert "moria" not in sm.configuration_values

    async def test_entry_exit_action_ordering(self, sm_runner):
        """on_exit fires before on_enter (verified via log)."""
        log = []

        class ActionOrderTracker(StateChart):
            class realm(State.Compound):
                day = State(initial=True)
                night = State()

                sunset = day.to(night)

            outside = State(final=True)
            leave = realm.to(outside)

            def on_exit_day(self):
                log.append("exit_day")

            def on_exit_realm(self):
                log.append("exit_realm")

            def on_enter_outside(self):
                log.append("enter_outside")

        sm = await sm_runner.start(ActionOrderTracker)
        await sm_runner.send(sm, "leave")
        assert log == ["exit_day", "exit_realm", "enter_outside"]

    async def test_generic_enter_exit_state_param_is_symmetric(self, sm_runner):
        """Generic ``on_enter_state``/``on_exit_state`` bind ``state`` to the
        individual state being crossed, symmetrically in both directions.

        Regression test for #634: exiting a compound used to report the
        transition ``source`` for every exited state (``child`` twice), so the
        parent state was never observable. Entering already reported the
        individual state, so the two callbacks were asymmetric.
        """
        enters: list = []
        exits: list = []

        class SymmetricCompound(StateChart):
            orphan = State(initial=True)

            class parent(State.Compound):
                child = State()

            switch = orphan.to(parent.child) | parent.child.to(orphan)

            def on_enter_state(self, source, target, state):
                enters.append((source.id, target.id, state.id))

            def on_exit_state(self, source, target, state):
                exits.append((source.id, target.id, state.id))

        sm = await sm_runner.start(SymmetricCompound)
        enters.clear()
        exits.clear()

        # Enter the compound: `state`/`target` track each entered state.
        await sm_runner.send(sm, "switch")
        assert enters == [
            ("orphan", "parent", "parent"),
            ("orphan", "child", "child"),
        ]
        assert exits == [("orphan", "child", "orphan")]

        enters.clear()
        exits.clear()

        # Exit the compound: `state`/`source` track each exited state, so the
        # parent is now distinguishable from the child.
        await sm_runner.send(sm, "switch")
        assert exits == [
            ("child", "orphan", "child"),
            ("parent", "orphan", "parent"),
        ]
        assert enters == [("child", "orphan", "orphan")]

    async def test_callbacks_inside_compound_class(self, sm_runner):
        """Methods defined inside the State.Compound class body are discovered."""
        log = []

        class CallbackDiscovery(StateChart):
            class realm(State.Compound):
                peaceful = State(initial=True)
                troubled = State()

                darken = peaceful.to(troubled)

                def on_enter_troubled(self):
                    log.append("entered troubled times")

            end = State(final=True)
            conclude = realm.to(end)

        sm = await sm_runner.start(CallbackDiscovery)
        await sm_runner.send(sm, "darken")
        assert log == ["entered troubled times"]

    async def test_done_state_inside_compound(self, sm_runner):
        """done_state_* bare transition inside a compound body registers done.state.* event."""

        class InnerDoneState(StateChart):
            class outer(State.Compound):
                class inner(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)

                    finish = start.to(end)

                after_inner = State(final=True)
                done_state_inner = inner.to(after_inner)

            victory = State(final=True)
            done_state_outer = outer.to(victory)

        sm = await sm_runner.start(InnerDoneState)
        assert "start" in sm.configuration_values

        await sm_runner.send(sm, "finish")
        assert {"victory"} == set(sm.configuration_values)

    async def test_done_invoke_inside_compound(self, sm_runner):
        """done_invoke_* bare transition inside a compound registers done.invoke.* event."""

        class InvokeInCompound(StateChart):
            class wrapper(State.Compound):
                loading = State(initial=True, invoke=lambda: 42)
                loaded = State(final=True)

                done_invoke_loading = loading.to(loaded)

            done = State(final=True)
            done_state_wrapper = wrapper.to(done)

        sm = await sm_runner.start(InvokeInCompound)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)
        assert {"done"} == set(sm.configuration_values)

    async def test_error_execution_inside_compound(self, sm_runner):
        """error_execution inside a compound body registers error.execution event."""

        def raise_error():
            raise RuntimeError("boom")

        class ErrorInCompound(StateChart):
            class active(State.Compound):
                ok = State(initial=True)
                failing = State()

                trigger = ok.to(failing, on=raise_error)

                errored = State()
                error_execution = failing.to(errored)

            done = State(final=True)
            finish = active.to(done)

        sm = await sm_runner.start(ErrorInCompound)
        await sm_runner.send(sm, "trigger")
        assert "errored" in sm.configuration_values

    def test_compound_state_name_attribute(self):
        """The name= kwarg in class syntax sets the state name."""

        class NamedCompound(StateChart):
            class shire(State.Compound, name="The Shire"):
                home = State(initial=True, final=True)

        sm = NamedCompound()
        assert sm.shire.name == "The Shire"

    async def test_from_enum_inside_compound(self, sm_runner):
        """States.from_enum() works inside compound states (#606)."""

        class OuterStates(Enum):
            FOO = auto()
            BAR = auto()

        class InnerStates(Enum):
            FIZZ = auto()
            BUZZ = auto()

        class SC(StateChart):
            baz = States.from_enum(OuterStates, initial=OuterStates.FOO, final=OuterStates.BAR)

            class inner(State.Compound):
                qux = States.from_enum(
                    InnerStates, initial=InnerStates.FIZZ, final=InnerStates.BUZZ
                )
                fizz_to_buzz = qux.FIZZ.to(qux.BUZZ)

            baz_foo_to_inner = baz.FOO.to(inner)
            inner_to_baz_bar = inner.to(baz.BAR)

        sm = await sm_runner.start(SC)
        assert {OuterStates.FOO} == set(sm.configuration_values)

        await sm_runner.send(sm, "baz_foo_to_inner")
        assert {"inner", InnerStates.FIZZ} == set(sm.configuration_values)

        await sm_runner.send(sm, "fizz_to_buzz")
        assert {"inner", InnerStates.BUZZ} == set(sm.configuration_values)

        await sm_runner.send(sm, "inner_to_baz_bar")
        assert {OuterStates.BAR} == set(sm.configuration_values)
