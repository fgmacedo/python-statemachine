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
from tests.machines.donedata.destroy_the_ring import DestroyTheRing
from tests.machines.donedata.destroy_the_ring_simple import DestroyTheRingSimple
from tests.machines.donedata.nested_quest_donedata import NestedQuestDoneData
from tests.machines.donedata.quest_for_erebor_done_convention import QuestForEreborDoneConvention
from tests.machines.donedata.quest_for_erebor_explicit_id import QuestForEreborExplicitId
from tests.machines.donedata.quest_for_erebor_multi_word import QuestForEreborMultiWord
from tests.machines.donedata.quest_for_erebor_with_event import QuestForEreborWithEvent


@pytest.mark.timeout(5)
class TestDoneData:
    async def test_donedata_callable_returns_dict(self, sm_runner):
        """Handler receives donedata as kwargs."""
        sm = await sm_runner.start(DestroyTheRing)
        await sm_runner.send(sm, "finish")
        assert sm.received["ring_destroyed"] is True
        assert sm.received["hero"] == "frodo"

    async def test_donedata_fires_done_state_with_data(self, sm_runner):
        """done.state event fires and triggers a transition."""
        sm = await sm_runner.start(DestroyTheRingSimple)
        await sm_runner.send(sm, "finish")
        assert {"celebration"} == set(sm.configuration_values)

    async def test_donedata_in_nested_compound(self, sm_runner):
        """Inner done.state propagates up through nesting."""
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

        class DestroyTheRingWithListener(StateChart):
            class quest(State.Compound):
                traveling = State(initial=True)
                completed = State(final=True, donedata="get_result")

                finish = traveling.to(completed)

                def get_result(self):
                    return {"ring_destroyed": True}

            celebration = State(final=True)
            done_state_quest = Event(quest.to(celebration))

        listener = QuestListener()
        sm = await sm_runner.start(DestroyTheRingWithListener, listeners=[listener])
        await sm_runner.send(sm, "finish")
        assert {"celebration"} == set(sm.configuration_values)


@pytest.mark.timeout(5)
class TestDoneStateConvention:
    async def test_done_state_convention_with_transition_list(self, sm_runner):
        """Bare TransitionList with done_state_ name auto-registers done.state.X."""
        sm = await sm_runner.start(QuestForEreborDoneConvention)
        await sm_runner.send(sm, "finish")
        assert {"celebration"} == set(sm.configuration_values)

    async def test_done_state_convention_with_event_no_explicit_id(self, sm_runner):
        """Event() wrapper without explicit id= applies the convention."""
        sm = await sm_runner.start(QuestForEreborWithEvent)
        await sm_runner.send(sm, "finish")
        assert {"celebration"} == set(sm.configuration_values)

    async def test_done_state_convention_preserves_explicit_id(self, sm_runner):
        """Explicit id= takes precedence over the convention."""
        sm = await sm_runner.start(QuestForEreborExplicitId)
        await sm_runner.send(sm, "finish")
        assert {"celebration"} == set(sm.configuration_values)

    async def test_done_state_convention_with_multi_word_state(self, sm_runner):
        """done_state_lonely_mountain maps to done.state.lonely_mountain."""
        sm = await sm_runner.start(QuestForEreborMultiWord)
        await sm_runner.send(sm, "enter_mountain")
        assert {"victory"} == set(sm.configuration_values)
