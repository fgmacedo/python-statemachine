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
    def test_donedata_callable_returns_dict(self):
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
            done_state_quest = Event(
                quest.to(epilogue, on="capture_result"), id="done.state.quest"
            )

            def capture_result(self, ring_destroyed=None, hero=None, **kwargs):
                received["ring_destroyed"] = ring_destroyed
                received["hero"] = hero

        sm = DestroyTheRing()
        sm.send("finish")
        assert received["ring_destroyed"] is True
        assert received["hero"] == "frodo"

    def test_donedata_fires_done_state_with_data(self):
        """done.state event fires and triggers a transition."""

        class DestroyTheRing(StateChart):
            class quest(State.Compound):
                traveling = State(initial=True)
                completed = State(final=True, donedata="get_result")

                finish = traveling.to(completed)

                def get_result(self):
                    return {"outcome": "victory"}

            celebration = State(final=True)
            done_state_quest = Event(quest.to(celebration), id="done.state.quest")

        sm = DestroyTheRing()
        sm.send("finish")
        assert {"celebration"} == set(sm.configuration_values)

    def test_donedata_in_nested_compound(self):
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
                done_state_inner = Event(inner.to(after_inner), id="done.state.inner")

            final = State(final=True)
            done_state_outer = Event(outer.to(final), id="done.state.outer")

        sm = NestedQuestDoneData()
        sm.send("go")
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

    def test_donedata_with_listener(self):
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
            done_state_quest = Event(quest.to(celebration), id="done.state.quest")

        listener = QuestListener()
        sm = DestroyTheRing(listeners=[listener])
        sm.send("finish")
        assert {"celebration"} == set(sm.configuration_values)
