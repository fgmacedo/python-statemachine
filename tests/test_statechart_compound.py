"""Compound state behavior using Python class syntax.

Tests exercise entering/exiting compound states, nested compounds, cross-compound
transitions, done.state events from final children, callback ordering, and discovery
of methods defined inside State.Compound class bodies.

Theme: Fellowship journey through Middle-earth.
"""

from enum import Enum
from enum import auto

import pytest
from statemachine.exceptions import InvalidDefinition
from statemachine.states import States

from statemachine import Event
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

    @pytest.mark.parametrize(
        "declare", [lambda transitions: transitions, Event], ids=["bare", "Event"]
    )
    async def test_error_execution_inside_compound(self, sm_runner, declare):
        """error_execution inside a compound body registers error.execution event."""

        def raise_error():
            raise RuntimeError("boom")

        class ErrorInCompound(StateChart):
            class active(State.Compound):
                ok = State(initial=True)
                failing = State()

                trigger = declare(ok.to(failing, on=raise_error))

                errored = State()
                error_execution = declare(failing.to(errored))

            done = State(final=True)
            finish = active.to(done)

        assert "error.execution" in [event.id for event in ErrorInCompound.events]

        sm = await sm_runner.start(ErrorInCompound)
        assert "ok" in sm.configuration_values

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


@pytest.mark.timeout(5)
class TestEventClassInsideCompound:
    """The ``Event`` class inside a ``State.Compound`` body (#643)."""

    async def test_event_class_declares_a_named_event(self, sm_runner):
        """``Event(<transition>)`` binds the event instead of leaving it eventless."""

        class QuirkyJourney(StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State()

                visit_pub = Event(bag_end.to(green_dragon))

            road = State(final=True)
            depart = Event(shire.to(road))

        assert [event.id for event in QuirkyJourney.events] == ["visit_pub", "depart"]

        sm = await sm_runner.start(QuirkyJourney)
        assert {"shire", "bag_end"} == set(sm.configuration_values)

        await sm_runner.send(sm, "visit_pub")
        assert {"shire", "green_dragon"} == set(sm.configuration_values)

    @pytest.mark.parametrize(
        ("declared", "expected"),
        [
            pytest.param({"delay": 50}, (50, False), id="delay"),
            pytest.param({"internal": True}, (0, True), id="internal"),
        ],
    )
    def test_name_delay_and_internal_are_preserved(self, declared, expected):
        class NamedEvent(StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State(final=True)

                visit_pub = Event(bag_end.to(green_dragon), name="Visit the pub", **declared)

        (registered,) = NamedEvent.events
        assert (registered.id, registered.name) == ("visit_pub", "Visit the pub")
        assert (registered.delay, registered.internal) == expected
        assert NamedEvent.visit_pub.name == "Visit the pub"

    def test_expanded_id_keeps_the_declared_arguments_on_both_ids(self):
        class ErrorEvent(StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State(final=True)

                error_foo = Event(bag_end.to(green_dragon), name="Boom", delay=50)

        assert [event.id for event in ErrorEvent.events] == ["error_foo", "error.foo"]
        assert [event.name for event in ErrorEvent.events] == ["Boom", "Boom"]
        assert [event.delay for event in ErrorEvent.events] == [50, 50]

    async def test_explicit_id_wins_over_the_attribute_name(self, sm_runner):
        class ExplicitId(StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State(final=True)

                visit_pub = Event(bag_end.to(green_dragon), id="pub.visit")

        assert [event.id for event in ExplicitId.events] == ["pub.visit"]

        sm = await sm_runner.start(ExplicitId)
        await sm_runner.send(sm, "pub.visit")
        assert {"shire", "green_dragon"} == set(sm.configuration_values)

    async def test_combined_transitions(self, sm_runner):
        class Wandering(StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State()

                wander = Event(bag_end.to(green_dragon) | green_dragon.to(bag_end))

            road = State(final=True)
            depart = Event(shire.to(road))

        sm = await sm_runner.start(Wandering)
        await sm_runner.send(sm, "wander")
        assert "green_dragon" in sm.configuration_values

        await sm_runner.send(sm, "wander")
        assert "bag_end" in sm.configuration_values

    async def test_event_inside_parallel_region(self, sm_runner):
        class WarOfTheRing(StateChart):
            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)

                    go = Event(start.to(end))

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)

                    victory = Event(fighting.to(won))

        sm = await sm_runner.start(WarOfTheRing)
        assert {"war", "quest", "start", "battle", "fighting"} == set(sm.configuration_values)

        await sm_runner.send(sm, "go")
        await sm_runner.send(sm, "victory")
        assert {"war", "quest", "end", "battle", "won"} == set(sm.configuration_values)

    def test_transition_less_event_declares_nothing(self):
        """A nested ``Event`` carries only its id, so with no transitions it is dropped."""

        class Placeholder(StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State(final=True)

                visit_pub = bag_end.to(green_dragon)
                knock = Event(name="Knock on the door")

        assert [event.id for event in Placeholder.events] == ["visit_pub"]
        assert not hasattr(Placeholder, "knock")


@pytest.mark.timeout(5)
class TestDecoratorEventInsideCompound:
    """The ``@<source>.to(<target>)`` decorator inside a ``State.Compound`` body."""

    async def test_decorator_declares_a_named_event(self, sm_runner):
        """The decorated name becomes the event, and its body runs as the ``on`` action."""

        class Gate(StateChart):
            class gate(State.Compound):
                locked = State(initial=True)
                unlocked = State()

                push = unlocked.to(locked)

                @locked.to(unlocked)
                def coin(self):
                    return "accepted"

            broken = State(final=True)
            smash = gate.to(broken)

        assert "coin" in [event.id for event in Gate.events]

        sm = await sm_runner.start(Gate)
        assert "locked" in sm.configuration_values

        assert await sm_runner.send(sm, "coin") == "accepted"
        assert "unlocked" in sm.configuration_values

    async def test_decorated_callback_is_not_an_event(self, sm_runner):
        """``@<event>.on`` keeps declaring a plain callback, not a new event."""

        log = []

        class Gate(StateChart):
            class gate(State.Compound):
                locked = State(initial=True)
                unlocked = State(final=True)

                coin = locked.to(unlocked)

                @coin.on
                def clink(self):
                    log.append("clink")

        assert [event.id for event in Gate.events] == ["coin"]

        sm = await sm_runner.start(Gate)
        await sm_runner.send(sm, "coin")
        assert log == ["clink"]


class TestCallbackNameCollision:
    """A callback referenced by object runs in every nested body that declares it; a name
    resolved by name in two bodies is an error instead of a silently discarded body (#653)."""

    async def test_decorator_event_in_sibling_regions(self, sm_runner):
        log = []

        class War(StateChart):
            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)

                    @start.to(end)
                    def go(self):
                        log.append("quest")

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)

                    @fighting.to(won)
                    def go(self):
                        log.append("battle")

        sm = await sm_runner.start(War)
        await sm_runner.send(sm, "go")
        assert sorted(log) == ["battle", "quest"]
        assert {"end", "won"} <= set(sm.configuration_values)

    async def test_decorated_action_in_sibling_regions(self, sm_runner):
        log = []

        class War(StateChart):
            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)
                    go = start.to(end)

                    @start.exit
                    def leave(self):
                        log.append("quest")

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)
                    go = fighting.to(won)

                    @fighting.exit
                    def leave(self):
                        log.append("battle")

        sm = await sm_runner.start(War)
        await sm_runner.send(sm, "go")
        assert sorted(log) == ["battle", "quest"]

    async def test_guard_object_in_sibling_regions(self, sm_runner):
        class War(StateChart):
            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)

                    def ready(self):
                        return True

                    go = start.to(end, cond=ready)

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)

                    def ready(self):
                        return False

                    go = fighting.to(won, cond=ready)

        sm = await sm_runner.start(War)
        await sm_runner.send(sm, "go")
        assert "end" in sm.configuration_values
        assert "fighting" in sm.configuration_values

    def test_decorated_callback_named_as_a_class_body_method(self):
        with pytest.raises(InvalidDefinition) as exc_info:

            class Journey(StateChart):
                class shire(State.Compound):
                    bag_end = State(initial=True)
                    green_dragon = State(final=True)
                    visit_pub = bag_end.to(green_dragon)

                    @bag_end.exit
                    def ready(self):
                        return "shire"

                road = State(final=True)
                leave = shire.to(road)

                def ready(self):
                    return "class"

        assert str(exc_info.value) == (
            "Callback 'ready' is declared in both the 'shire' state body and the 'Journey' "
            "class body. Nested state bodies share the class namespace. Rename one of them."
        )

    @pytest.mark.parametrize("decorated", [False, True])
    async def test_nested_callback_overrides_an_inherited_method(self, sm_runner, decorated):
        class Guards:
            def ready(self):
                return "base"

        class Journey(Guards, StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State(final=True)
                visit_pub = bag_end.to(green_dragon)

                if decorated:

                    @bag_end.exit
                    def ready(self):
                        return "nested"

                else:

                    def ready(self):
                        return "nested"

        sm = await sm_runner.start(Journey)
        assert sm.ready() == "nested"

    async def test_subclass_leaves_base_callbacks_untouched(self, sm_runner):
        log = []

        def arrive(self):
            log.append(type(self).__name__)

        class Model:
            pass

        Model.arrive = arrive

        class Base(StateChart):
            validate_trap_states = False
            validate_disconnected_states = False
            idle = State(initial=True, enter=arrive)

        class Sub(Base):  # noqa: F841
            class extra(State.Compound):
                start = State(initial=True)
                on_arrive = arrive

            class other(State.Compound):
                begin = State(initial=True)

                @begin.enter
                def arrive(self):
                    log.append("other")

        await sm_runner.start(Base, model=Model())
        assert log == ["Model"]

    async def test_string_literal_in_a_guard_does_not_block_storing_apart(self, sm_runner):
        log = []

        class War(StateChart):
            mode = "audit"

            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)
                    go = start.to(end, cond="mode == 'audit'")

                    @end.enter
                    def audit(self):
                        log.append("quest")

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)
                    go = fighting.to(won)

                    @won.enter
                    def audit(self):
                        log.append("battle")

        sm = await sm_runner.start(War)
        await sm_runner.send(sm, "go")
        assert sorted(log) == ["battle", "quest"]

    def test_plain_callback_named_as_a_class_body_event(self):
        with pytest.raises(InvalidDefinition) as exc_info:

            class Gate(StateChart):
                class gate(State.Compound):
                    closed = State(initial=True)
                    opened = State(final=True)
                    push = closed.to(opened)

                    def kick(self):
                        return True

                broken = State(final=True)
                kick = gate.to(broken)

        assert str(exc_info.value) == (
            "Callback 'kick' in the 'gate' state body clashes with the event 'kick'. "
            "Nested state bodies share the class namespace. Rename one of them."
        )

    def test_decorated_callback_beside_a_plain_helper_of_the_same_name(self):
        with pytest.raises(InvalidDefinition, match="Callback 'limit' is declared in both"):

            class War(StateChart):
                class war(State.Parallel):
                    class quest(State.Compound):
                        start = State(initial=True)
                        end = State(final=True)

                        def limit(self):
                            return 10

                        go = start.to(end, cond=limit)

                    class battle(State.Compound):
                        fighting = State(initial=True)
                        won = State(final=True)
                        victory = fighting.to(won)

                        def limit(self):
                            return 0

    def test_decorated_callback_whose_name_is_used_by_a_string_reference(self):
        with pytest.raises(InvalidDefinition, match="Callback 'ok' is declared in both"):

            class War(StateChart):
                class war(State.Parallel):
                    class quest(State.Compound):
                        start = State(initial=True)
                        end = State(final=True)
                        go = start.to(end, cond="ok")

                        @start.enter
                        def ok(self):
                            return True

                    class battle(State.Compound):
                        fighting = State(initial=True)
                        won = State(final=True)
                        victory = fighting.to(won)

                        @fighting.enter
                        def ok(self):
                            return False

    def test_decorated_callbacks_named_by_a_naming_convention(self):
        with pytest.raises(InvalidDefinition, match="Callback 'on_enter_end' is declared in both"):

            class War(StateChart):
                class war(State.Parallel):
                    class battle(State.Compound):
                        fighting = State(initial=True)
                        won = State(final=True)
                        go = fighting.to(won)

                        @won.enter
                        def on_enter_end(self):
                            return "battle"

                    class quest(State.Compound):
                        start = State(initial=True)
                        end = State(final=True)
                        go = start.to(end)

                        @end.enter
                        def on_enter_end(self):
                            return "quest"

    async def test_subclass_runs_callbacks_stored_apart(self, sm_runner):
        log = []

        class War(StateChart):
            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)

                    @start.to(end)
                    def go(self):
                        log.append("quest")

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)

                    @fighting.to(won)
                    def go(self):
                        log.append("battle")

        class Campaign(War):
            pass

        sm = await sm_runner.start(Campaign)
        await sm_runner.send(sm, "go")
        assert sorted(log) == ["battle", "quest"]

    async def test_stored_apart_callback_survives_reuse_by_another_machine(self, sm_runner):
        log = []

        def arrive(self):
            log.append("quest")

        class War(StateChart):
            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)
                    go = start.to(end)

                    on_arrive = end.enter(arrive)

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)
                    go = fighting.to(won)

                    @won.enter
                    def arrive(self):
                        log.append("battle")

        class Errand(StateChart):
            home = State(initial=True)
            market = State(final=True)
            go = home.to(market, on=arrive)

        sm = await sm_runner.start(War)
        await sm_runner.send(sm, "go")
        assert sorted(log) == ["battle", "quest"]

    async def test_decorated_callback_named_as_a_sibling_event(self, sm_runner):
        log = []

        class War(StateChart):
            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)
                    step = start.to(end)

                    @start.exit
                    def go(self):
                        log.append("quest")

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)
                    go = fighting.to(won)

        sm = await sm_runner.start(War)
        await sm_runner.send(sm, "go")
        assert "won" in sm.configuration_values
        await sm_runner.send(sm, "step")
        assert log == ["quest"]

    def test_plain_callback_in_sibling_regions(self):
        with pytest.raises(InvalidDefinition, match="Callback 'on_enter_end' is declared in both"):

            class War(StateChart):
                class war(State.Parallel):
                    class quest(State.Compound):
                        start = State(initial=True)
                        end = State(final=True)
                        go = start.to(end)

                        def on_enter_end(self):
                            return "quest"

                    class battle(State.Compound):
                        fighting = State(initial=True)
                        won = State(final=True)
                        victory = fighting.to(won)

                        def on_enter_end(self):
                            return "battle"

    def test_callback_in_parent_and_child_bodies(self):
        with pytest.raises(InvalidDefinition) as exc_info:

            class Journey(StateChart):
                class moria(State.Compound):
                    class halls(State.Compound, initial=True):
                        entrance = State(initial=True)
                        bridge = State(final=True)
                        cross = entrance.to(bridge)

                        def on_enter_bridge(self):
                            return "halls"

                    daylight = State(final=True)
                    escape = halls.to(daylight)

                    def on_enter_bridge(self):
                        return "moria"

        assert "'moria' and the 'halls' state bodies" in str(exc_info.value)

    def test_callback_in_state_body_and_class_body(self):
        with pytest.raises(InvalidDefinition) as exc_info:

            class Journey(StateChart):
                class shire(State.Compound):
                    bag_end = State(initial=True)
                    green_dragon = State(final=True)
                    visit_pub = bag_end.to(green_dragon)

                    def on_enter_green_dragon(self):
                        return "shire"

                def on_enter_green_dragon(self):
                    return "class"

        assert str(exc_info.value) == (
            "Callback 'on_enter_green_dragon' is declared in both the 'shire' state body and "
            "the 'Journey' class body. Nested state bodies share the class namespace. "
            "Rename one of them."
        )

    async def test_decorator_event_in_state_body_and_class_body(self, sm_runner):
        log = []

        class Journey(StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State()

                @bag_end.to(green_dragon)
                def go(self):
                    log.append("shire")

            road = State(final=True)

            @shire.to(road)
            def go(self):
                log.append("class")

        sm = await sm_runner.start(Journey)
        await sm_runner.send(sm, "go")
        assert log == ["shire"]
        await sm_runner.send(sm, "go")
        assert log == ["shire", "class"]

    async def test_same_function_in_sibling_regions_is_not_a_collision(self, sm_runner):
        log = []

        def arrive(self):
            log.append("arrived")

        class War(StateChart):
            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)
                    go = start.to(end)

                    on_enter_end = arrive

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)
                    victory = fighting.to(won)

                    on_enter_end = arrive

        sm = await sm_runner.start(War)
        await sm_runner.send(sm, "go")
        assert log == ["arrived"]

    async def test_same_function_in_state_body_and_class_body_is_not_a_collision(self, sm_runner):
        log = []

        def arrive(self):
            log.append("arrived")

        class Journey(StateChart):
            class shire(State.Compound):
                bag_end = State(initial=True)
                green_dragon = State(final=True)
                visit_pub = bag_end.to(green_dragon)

                on_enter_green_dragon = arrive

            on_enter_green_dragon = arrive

        sm = await sm_runner.start(Journey)
        await sm_runner.send(sm, "visit_pub")
        assert log == ["arrived"]

    async def test_same_decorated_function_in_sibling_regions(self, sm_runner):
        log = []

        def arrive(self):
            log.append("arrived")

        class War(StateChart):
            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)
                    go = start.to(end)

                    on_arrive = end.enter(arrive)

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)
                    go = fighting.to(won)

                    on_arrive = won.enter(arrive)

        sm = await sm_runner.start(War)
        await sm_runner.send(sm, "go")
        assert log == ["arrived", "arrived"]

    async def test_same_bound_method_in_sibling_regions_is_not_a_collision(self, sm_runner):
        class Chronicle:
            def __init__(self):
                self.log = []

            def arrive(self):
                self.log.append("arrived")

        chronicle = Chronicle()

        class War(StateChart):
            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)
                    go = start.to(end)

                    on_enter_end = chronicle.arrive

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)
                    victory = fighting.to(won)

                    on_enter_end = chronicle.arrive

        sm = await sm_runner.start(War)
        await sm_runner.send(sm, "go")
        assert chronicle.log == ["arrived"]

    def test_callback_named_as_an_event_of_a_sibling_region(self):
        with pytest.raises(InvalidDefinition) as exc_info:

            class War(StateChart):
                class war(State.Parallel):
                    class quest(State.Compound):
                        start = State(initial=True)
                        end = State(final=True)
                        step = start.to(end, cond="go")

                        def go(self):
                            return True

                    class battle(State.Compound):
                        fighting = State(initial=True)
                        won = State(final=True)
                        go = fighting.to(won)

        assert str(exc_info.value) == (
            "Callback 'go' in the 'quest' state body clashes with the event 'go'. "
            "Nested state bodies share the class namespace. Rename one of them."
        )

    @pytest.mark.parametrize("attribute", ["name", "states"])
    def test_callback_named_as_a_class_attribute(self, attribute):
        def callback(self):
            return "Frodo"

        callback.__name__ = attribute

        with pytest.raises(InvalidDefinition) as exc_info:

            class Journey(StateChart):
                class shire(State.Compound):
                    bag_end = State(initial=True)
                    green_dragon = State(final=True)
                    visit_pub = bag_end.to(green_dragon, on=attribute)

                    locals()[attribute] = callback

        assert str(exc_info.value) == (
            f"Callback '{attribute}' in the 'shire' state body clashes with the "
            f"'{attribute}' attribute of 'Journey'. Nested state bodies share the class "
            "namespace. Rename one of them."
        )

    async def test_distinct_names_in_sibling_regions_both_run(self, sm_runner):
        log = []

        class War(StateChart):
            class war(State.Parallel):
                class quest(State.Compound):
                    start = State(initial=True)
                    end = State(final=True)

                    @start.to(end)
                    def go(self):
                        log.append("quest")

                class battle(State.Compound):
                    fighting = State(initial=True)
                    won = State(final=True)

                    @fighting.to(won)
                    def victory(self):
                        log.append("battle")

        sm = await sm_runner.start(War)
        await sm_runner.send(sm, "go")
        await sm_runner.send(sm, "victory")
        assert log == ["quest", "battle"]


def _journey_with_callback(form: str, log: list):
    """A chart whose compound body declares one callback in the given ``form``.

    Every form appends ``"base"`` to ``log`` when ``visit_pub`` runs.
    """

    class Journey(StateChart):
        class shire(State.Compound):
            bag_end = State(initial=True)
            green_dragon = State()

            visit_pub = bag_end.to(green_dragon)

            if form == "method":

                def on_enter_green_dragon(self):
                    log.append("base")

            elif form == "on":

                @visit_pub.on
                def toast(self):
                    log.append("base")

            elif form == "cond":

                @visit_pub.cond
                def pub_open(self):
                    log.append("base")
                    return True

        road = State(final=True)
        depart = shire.to(road)

    return Journey


@pytest.mark.timeout(5)
class TestSubclassingCompoundWithCallbacks:
    """Subclassing a chart whose compound body declares callbacks.

    The base class and its subclasses share the same nested ``State`` objects, so unpacking
    the callbacks of the body must not break the next class built from them.
    """

    FORMS = ["method", "on", "cond"]

    @pytest.fixture(params=FORMS)
    def form(self, request):
        return request.param

    @pytest.fixture()
    def log(self):
        return []

    @pytest.fixture()
    def Journey(self, form, log):
        return _journey_with_callback(form, log)

    async def test_subclass_inherits_the_nested_callback(self, sm_runner, Journey, log):
        class Child(Journey):
            pass

        assert Child.shire is Journey.shire

        sm = await sm_runner.start(Child)
        await sm_runner.send(sm, "visit_pub")
        assert log == ["base"]
        assert "green_dragon" in sm.configuration_values

    async def test_base_keeps_working_after_being_subclassed(self, sm_runner, Journey, log):
        """Building the subclass must not consume the callbacks the base still runs."""

        class Child(Journey):
            pass

        sm = await sm_runner.start(Journey)
        await sm_runner.send(sm, "visit_pub")
        assert log == ["base"]

    async def test_second_level_subclass(self, sm_runner, Journey, log):
        class Child(Journey):
            pass

        class GrandChild(Child):
            pass

        sm = await sm_runner.start(GrandChild)
        await sm_runner.send(sm, "visit_pub")
        assert log == ["base"]

    @pytest.mark.parametrize("form", ["method"])
    async def test_subclass_overrides_the_nested_callback(self, sm_runner, Journey, log):
        """Only the naming convention supports overriding, in a nested body as at the top level.

        A callback declared through ``@<event>.on`` or ``@<event>.cond`` is resolved by the
        identity of the decorated function: a subclass method of the same name is not picked
        up, and the original is dropped with it.
        """

        class Child(Journey):
            def on_enter_green_dragon(self):
                log.append("child")

        sm = await sm_runner.start(Child)
        await sm_runner.send(sm, "visit_pub")
        assert log == ["child"]

        log.clear()
        sm = await sm_runner.start(Journey)
        await sm_runner.send(sm, "visit_pub")
        assert log == ["base"]

    @pytest.mark.parametrize("form", ["method"])
    async def test_second_level_subclass_keeps_the_override(self, sm_runner, Journey, log):
        class Child(Journey):
            def on_enter_green_dragon(self):
                log.append("child")

        class GrandChild(Child):
            pass

        sm = await sm_runner.start(GrandChild)
        await sm_runner.send(sm, "visit_pub")
        assert log == ["child"]

    @pytest.mark.parametrize("form", ["method"])
    async def test_second_level_subclass_keeps_the_callback_disabled(
        self, sm_runner, Journey, log
    ):
        class Child(Journey):
            on_enter_green_dragon = None

        class GrandChild(Child):
            pass

        sm = await sm_runner.start(GrandChild)
        await sm_runner.send(sm, "visit_pub")
        assert log == []
        assert "green_dragon" in sm.configuration_values

    async def test_subclass_adds_its_own_callback(self, sm_runner, Journey, log, form):
        class Child(Journey):
            def on_exit_bag_end(self):
                log.append("child")

        sm = await sm_runner.start(Child)
        await sm_runner.send(sm, "visit_pub")
        guard_runs_first = form == "cond"
        assert log == (["base", "child"] if guard_runs_first else ["child", "base"])

    async def test_parallel_body_with_callback(self, sm_runner, log):
        class Beacons(StateChart):
            class beacons(State.Parallel):
                class amon_din(State.Compound):
                    dark = State(initial=True)
                    lit = State()

                    kindle = dark.to(lit)

                    def on_enter_lit(self):
                        log.append("base")

                class eilenach(State.Compound):
                    idle = State(initial=True)

        class Child(Beacons):
            pass

        sm = await sm_runner.start(Child)
        await sm_runner.send(sm, "kindle")
        assert log == ["base"]
