"""Compound state behavior using Python class syntax.

Tests exercise entering/exiting compound states, nested compounds, cross-compound
transitions, done.state events from final children, callback ordering, and discovery
of methods defined inside State.Compound class bodies.

Theme: Fellowship journey through Middle-earth.
"""

import pytest

from statemachine import State
from statemachine import StateChart


@pytest.mark.timeout(5)
class TestCompoundStates:
    async def test_enter_compound_activates_initial_child(self, sm_runner):
        """Entering a compound activates both parent and the initial child."""

        class ShireToRivendell(StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State()

                visit_pub = bag_end.to(green_dragon)

            road = State(final=True)
            depart = shire.to(road)

        sm = await sm_runner.start(ShireToRivendell)
        assert {"shire", "bag_end"} == set(sm.configuration_values)

    async def test_transition_within_compound(self, sm_runner):
        """Inner state changes while parent stays active."""

        class ShireToRivendell(StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State()

                visit_pub = bag_end.to(green_dragon)

            road = State(final=True)
            depart = shire.to(road)

        sm = await sm_runner.start(ShireToRivendell)
        await sm_runner.send(sm, "visit_pub")
        assert "shire" in sm.configuration_values
        assert "green_dragon" in sm.configuration_values
        assert "bag_end" not in sm.configuration_values

    async def test_exit_compound_removes_all_descendants(self, sm_runner):
        """Leaving a compound removes the parent and all children."""

        class ShireToRivendell(StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State()

                visit_pub = bag_end.to(green_dragon)

            road = State(final=True)
            depart = shire.to(road)

        sm = await sm_runner.start(ShireToRivendell)
        await sm_runner.send(sm, "depart")
        assert {"road"} == set(sm.configuration_values)

    async def test_nested_compound_two_levels(self, sm_runner):
        """Three-level nesting: outer > middle > leaf."""

        class MoriaExpedition(StateChart):
            class moria(State.Compound):
                class upper_halls(State.Compound):
                    entrance = State(initial=True)
                    bridge = State(final=True)

                    cross = entrance.to(bridge)

                assert isinstance(upper_halls, State)
                depths = State(final=True)
                descend = upper_halls.to(depths)

        sm = await sm_runner.start(MoriaExpedition)
        assert {"moria", "upper_halls", "entrance"} == set(sm.configuration_values)

    async def test_transition_from_inner_to_outer(self, sm_runner):
        """A deep child can transition to an outer state."""

        class MoriaExpedition(StateChart):
            class moria(State.Compound):
                class upper_halls(State.Compound):
                    entrance = State(initial=True)
                    bridge = State()

                    cross = entrance.to(bridge)

                assert isinstance(upper_halls, State)
                depths = State(final=True)
                descend = upper_halls.to(depths)

            daylight = State(final=True)
            escape = moria.to(daylight)

        sm = await sm_runner.start(MoriaExpedition)
        await sm_runner.send(sm, "escape")
        assert {"daylight"} == set(sm.configuration_values)

    async def test_cross_compound_transition(self, sm_runner):
        """Transition from one compound to another removes old children."""

        class MiddleEarthJourney(StateChart):
            validate_disconnected_states = False

            class rivendell(State.Compound):
                council = State(initial=True)
                preparing = State()

                get_ready = council.to(preparing)

            class moria(State.Compound):
                gates = State(initial=True)
                bridge = State(final=True)

                cross = gates.to(bridge)

            class lothlorien(State.Compound):
                mirror = State(initial=True)
                departure = State(final=True)

                leave = mirror.to(departure)

            march_to_moria = rivendell.to(moria)
            march_to_lorien = moria.to(lothlorien)

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

        class MiddleEarthJourney(StateChart):
            validate_disconnected_states = False

            class rivendell(State.Compound):
                council = State(initial=True)
                preparing = State()

                get_ready = council.to(preparing)

            class moria(State.Compound):
                gates = State(initial=True)
                bridge = State(final=True)

                cross = gates.to(bridge)

            march_to_moria = rivendell.to(moria)

        sm = await sm_runner.start(MiddleEarthJourney)
        await sm_runner.send(sm, "march_to_moria")
        assert "gates" in sm.configuration_values
        assert "moria" in sm.configuration_values

    async def test_final_child_fires_done_state(self, sm_runner):
        """Reaching a final child triggers done.state.{parent_id}."""

        class QuestForErebor(StateChart):
            class lonely_mountain(State.Compound):
                approach = State(initial=True)
                inside = State(final=True)

                enter_mountain = approach.to(inside)

            victory = State(final=True)
            done_state_lonely_mountain = lonely_mountain.to(victory)

        sm = await sm_runner.start(QuestForErebor)
        assert "approach" in sm.configuration_values

        await sm_runner.send(sm, "enter_mountain")
        assert {"victory"} == set(sm.configuration_values)

    async def test_multiple_compound_sequential_traversal(self, sm_runner):
        """Traverse all three compounds sequentially."""

        class MiddleEarthJourney(StateChart):
            validate_disconnected_states = False

            class rivendell(State.Compound):
                council = State(initial=True)
                preparing = State(final=True)

                get_ready = council.to(preparing)

            class moria(State.Compound):
                gates = State(initial=True)
                bridge = State(final=True)

                cross = gates.to(bridge)

            class lothlorien(State.Compound):
                mirror = State(initial=True)
                departure = State(final=True)

                leave = mirror.to(departure)

            march_to_moria = rivendell.to(moria)
            march_to_lorien = moria.to(lothlorien)

        sm = await sm_runner.start(MiddleEarthJourney)
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

    def test_compound_state_name_attribute(self):
        """The name= kwarg in class syntax sets the state name."""

        class NamedCompound(StateChart):
            class shire(State.Compound, name="The Shire"):
                home = State(initial=True, final=True)

        sm = NamedCompound()
        assert sm.shire.name == "The Shire"
