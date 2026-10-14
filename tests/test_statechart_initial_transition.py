"""Explicit initial transitions of compound states (refs #587)."""

import pytest
from statemachine.exceptions import InvalidDefinition

from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart


class DeepInitial(StateChart):
    class d(State.Compound):
        class d1(State.Compound):
            d11 = State(initial=True)

        class d2(State.Compound):
            class d21(State.Compound):
                d211 = State(initial=True)
                d212 = State()
                x = d211.to(d212)

        to_d2 = d1.to(d2)
        to_d1 = d2.to(d1)

    d.to(d.d2.d21.d212, initial=True, on="init_action")
    out = State()
    leave = d.to(out)
    back = out.to(d)

    def __init__(self, *args, **kwargs):
        self.log = []
        super().__init__(*args, **kwargs)

    def init_action(self):
        self.log.append("init_action")

    def on_enter_state(self, state):
        self.log.append(f"enter:{state.id}")


class TestExplicitInitialTransition:
    def test_is_the_only_initial_transition_of_the_compound(self):
        initials = [t for t in DeepInitial.d.transitions if t.initial]

        assert [t.target.id for t in initials] == ["d212"]

    def test_no_child_is_marked_initial_by_document_order(self):
        assert not DeepInitial.d.d1.initial

    async def test_effect_runs_between_parent_entry_and_child_entries(self, sm_runner):
        sm = await sm_runner.start(DeepInitial)

        assert set(sm.configuration_values) == {"d", "d2", "d21", "d212"}
        assert sm.log == ["enter:d", "init_action", "enter:d2", "enter:d21", "enter:d212"]

    async def test_effect_runs_again_on_reentry(self, sm_runner):
        sm = await sm_runner.start(DeepInitial)
        await sm_runner.send(sm, "leave")
        sm.log.clear()

        await sm_runner.send(sm, "back")

        assert set(sm.configuration_values) == {"d", "d2", "d21", "d212"}
        assert sm.log == ["enter:d", "init_action", "enter:d2", "enter:d21", "enter:d212"]

    async def test_effect_receives_event_arguments(self, sm_runner):
        received = []

        class Chart(StateChart):
            class d(State.Compound):
                a = State()
                b = State()
                back = b.to(a)

            out = State(initial=True)
            enter = out.to(d)
            d.to(d.b, initial=True, on=lambda value: received.append(value))

        sm = await sm_runner.start(Chart)
        await sm_runner.send(sm, "enter", value=42)

        assert set(sm.configuration_values) == {"d", "b"}
        assert received == [42]

    def test_subclass_keeps_a_single_initial_transition(self):
        class Child(DeepInitial):
            pass

        sm = Child()

        assert [t.target.id for t in Child.d.transitions if t.initial] == ["d212"]
        assert sm.log == ["enter:d", "init_action", "enter:d2", "enter:d21", "enter:d212"]


class TestConflictingInitialDefinitions:
    def test_two_explicit_initial_transitions_are_rejected(self):
        with pytest.raises(InvalidDefinition, match="d.*more than one initial transition"):

            class Chart(StateChart):
                class d(State.Compound):
                    a = State()
                    b = State()

                d.to(d.a, initial=True)
                d.to(d.b, initial=True)

    def test_initial_child_targeted_by_explicit_initial_transition_is_accepted(self):
        class Chart(StateChart):
            class d(State.Compound):
                a = State()
                b = State(initial=True)
                back = b.to(a)

            d.to(d.b, initial=True, on="effect")

            def effect(self):
                self.ran = True

        sm = Chart()

        assert [t.target.id for t in Chart.d.transitions if t.initial] == ["b"]
        assert set(sm.configuration_values) == {"d", "b"}
        assert sm.ran

    def test_initial_child_containing_the_explicit_target_is_accepted(self):
        class Chart(StateChart):
            class d(State.Compound):
                a = State()

                class b(State.Compound, initial=True):
                    b1 = State(initial=True)
                    b2 = State()
                    step = b2.to(b1)

                back = b.to(a)

            d.to(d.b.b2, initial=True)

        sm = Chart()

        assert set(sm.configuration_values) == {"d", "b", "b2"}


class TestInitialTransitionEffectErrors:
    async def test_error_in_effect_becomes_error_execution_and_entry_completes(self, sm_runner):
        class Chart(StateChart):
            class d(State.Compound):
                a = State()
                b = State()
                back = b.to(a)

            out = State(initial=True)
            go = out.to(d)
            d.to(d.b, initial=True, on="effect")

            def effect(self):
                raise ValueError("effect failed")

        sm = await sm_runner.start(Chart)
        await sm_runner.send(sm, "go")

        assert set(sm.configuration_values) == {"d", "b"}

    async def test_error_execution_handler_sees_the_effect_error(self, sm_runner):
        class Chart(StateChart):
            class d(State.Compound):
                a = State()
                b = State()
                back = b.to(a)

            out = State(initial=True)
            go = out.to(d)
            d.to(d.b, initial=True, on="effect")
            error_execution = d.to(out, on="handle")

            def __init__(self, *args, **kwargs):
                self.errors = []
                super().__init__(*args, **kwargs)

            def effect(self):
                raise ValueError("effect failed")

            def handle(self, error):
                self.errors.append(str(error))

        sm = await sm_runner.start(Chart)
        await sm_runner.send(sm, "go")

        assert sm.errors == ["effect failed"]
        assert set(sm.configuration_values) == {"out"}


class TestInitialTransitionToHistory:
    async def test_effect_runs_once_per_entry(self, sm_runner):
        class Chart(StateChart):
            class d(State.Compound):
                h = HistoryState()
                a = State()
                b = State()
                step = a.to(b)
                h.to(a)

            d.to(d.h, initial=True, on="effect")
            out = State()
            leave = d.to(out)
            back = out.to(d)

            def __init__(self, *args, **kwargs):
                self.effects = 0
                super().__init__(*args, **kwargs)

            def effect(self):
                self.effects += 1

        sm = await sm_runner.start(Chart)
        assert sm.effects == 1

        await sm_runner.send(sm, "step")
        await sm_runner.send(sm, "leave")
        await sm_runner.send(sm, "back")

        assert sm.effects == 2
        assert set(sm.configuration_values) == {"d", "b"}
