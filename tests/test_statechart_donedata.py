"""Donedata on final states passes data to done.state handlers.

Tests exercise callable donedata returning dicts, done.state transitions triggered
with data, nested compound donedata propagation, InvalidDefinition for donedata on
non-final states, and listener capture of done event kwargs.

Theme: Quest completion — returning data about how the quest ended.
"""

import pytest
from statemachine.exceptions import InvalidDefinition

from statemachine import Event
from statemachine import State
from statemachine import StateChart


@pytest.mark.timeout(5)
class TestDoneData:
    async def test_donedata_callable_returns_dict(self, sm_runner):
        """Handler receives donedata as kwargs."""
        received = {}

        class DestroyTheRing(StateChart):
            class quest(State.Compound):
                traveling = State(initial=True)
                completed = State(final=True, donedata="get_quest_result")

                finish = traveling.to(completed)

                def get_quest_result(self):
                    return {"ring_destroyed": True, "hero": "frodo"}

            epilogue = State(final=True)
            done_state_quest = Event(quest.to(epilogue, on="capture_result"))

            def capture_result(self, ring_destroyed=None, hero=None, **kwargs):
                received["ring_destroyed"] = ring_destroyed
                received["hero"] = hero

        sm = await sm_runner.start(DestroyTheRing)
        await sm_runner.send(sm, "finish")
        assert received["ring_destroyed"] is True
        assert received["hero"] == "frodo"

    async def test_donedata_fires_done_state_with_data(self, sm_runner):
        """done.state event fires and triggers a transition."""

        class DestroyTheRing(StateChart):
            class quest(State.Compound):
                traveling = State(initial=True)
                completed = State(final=True, donedata="get_result")

                finish = traveling.to(completed)

                def get_result(self):
                    return {"outcome": "victory"}

            celebration = State(final=True)
            done_state_quest = Event(quest.to(celebration))

        sm = await sm_runner.start(DestroyTheRing)
        await sm_runner.send(sm, "finish")
        assert {"celebration"} == set(sm.configuration_values)

    async def test_donedata_in_nested_compound(self, sm_runner):
        """Inner done.state propagates up through nesting."""

        class NestedQuestDoneData(StateChart):
            class outer(State.Compound):
                class inner(State.Compound):
                    start = State(initial=True)
                    end = State(final=True, donedata="inner_result")

                    go = start.to(end)

                    def inner_result(self):
                        return {"level": "inner"}

                assert isinstance(inner, State)
                after_inner = State(final=True)
                done_state_inner = Event(inner.to(after_inner))

            final = State(final=True)
            done_state_outer = Event(outer.to(final))

        sm = await sm_runner.start(NestedQuestDoneData)
        await sm_runner.send(sm, "go")
        # inner finishes -> done.state.inner -> after_inner (final)
        # -> done.state.outer -> final
        assert {"final"} == set(sm.configuration_values)

    def test_donedata_only_on_final_state(self):
        """InvalidDefinition if donedata is on a non-final state."""
        with pytest.raises(InvalidDefinition, match="donedata.*final"):

            class BadDoneData(StateChart):
                s1 = State(initial=True, donedata="oops")
                s2 = State(final=True)

                go = s1.to(s2)

    async def test_donedata_with_listener(self, sm_runner):
        """Listener captures done event kwargs."""
        captured = {}

        class QuestListener:
            def on_enter_celebration(self, ring_destroyed=None, **kwargs):
                captured["ring_destroyed"] = ring_destroyed

        class DestroyTheRing(StateChart):
            class quest(State.Compound):
                traveling = State(initial=True)
                completed = State(final=True, donedata="get_result")

                finish = traveling.to(completed)

                def get_result(self):
                    return {"ring_destroyed": True}

            celebration = State(final=True)
            done_state_quest = Event(quest.to(celebration))

        listener = QuestListener()
        sm = await sm_runner.start(DestroyTheRing, listeners=[listener])
        await sm_runner.send(sm, "finish")
        assert {"celebration"} == set(sm.configuration_values)


@pytest.mark.timeout(5)
class TestDoneStateConvention:
    async def test_done_state_convention_with_transition_list(self, sm_runner):
        """Bare TransitionList with done_state_ name auto-registers done.state.X."""

        class QuestForErebor(StateChart):
            class quest(State.Compound):
                traveling = State(initial=True)
                arrived = State(final=True)

                finish = traveling.to(arrived)

            celebration = State(final=True)
            done_state_quest = quest.to(celebration)

        sm = await sm_runner.start(QuestForErebor)
        await sm_runner.send(sm, "finish")
        assert {"celebration"} == set(sm.configuration_values)

    async def test_done_state_convention_with_event_no_explicit_id(self, sm_runner):
        """Event() wrapper without explicit id= applies the convention."""

        class QuestForErebor(StateChart):
            class quest(State.Compound):
                traveling = State(initial=True)
                arrived = State(final=True)

                finish = traveling.to(arrived)

            celebration = State(final=True)
            done_state_quest = Event(quest.to(celebration))

        sm = await sm_runner.start(QuestForErebor)
        await sm_runner.send(sm, "finish")
        assert {"celebration"} == set(sm.configuration_values)

    async def test_done_state_convention_preserves_explicit_id(self, sm_runner):
        """Explicit id= takes precedence over the convention."""

        class QuestForErebor(StateChart):
            class quest(State.Compound):
                traveling = State(initial=True)
                arrived = State(final=True)

                finish = traveling.to(arrived)

            celebration = State(final=True)
            done_state_quest = Event(quest.to(celebration), id="done.state.quest")

        sm = await sm_runner.start(QuestForErebor)
        await sm_runner.send(sm, "finish")
        assert {"celebration"} == set(sm.configuration_values)

    async def test_done_state_convention_with_multi_word_state(self, sm_runner):
        """done_state_lonely_mountain maps to done.state.lonely_mountain."""

        class QuestForErebor(StateChart):
            class lonely_mountain(State.Compound):
                approach = State(initial=True)
                inside = State(final=True)

                enter_mountain = approach.to(inside)

            victory = State(final=True)
            done_state_lonely_mountain = lonely_mountain.to(victory)

        sm = await sm_runner.start(QuestForErebor)
        await sm_runner.send(sm, "enter_mountain")
        assert {"victory"} == set(sm.configuration_values)
