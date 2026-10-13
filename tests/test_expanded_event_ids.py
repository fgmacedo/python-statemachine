"""Prefixed event attributes register one event per id they expand to.

``error_X``, ``done_state_X`` and ``done_invoke_X`` declare both the attribute name and the
SCXML dotted form, each as its own event: reachable as a method, sendable by id, and listed by
``allowed_events`` / ``enabled_events()``.

Theme: a hobbit leaving Bag End.
"""

from inspect import isawaitable

import pytest
from statemachine.contrib.diagram.extract import extract
from statemachine.event import _expand_event_id
from statemachine.state import NestedStateFactory
from statemachine.utils import humanize_id

from statemachine import Event
from statemachine import State
from statemachine import StateChart

PREFIXES = [
    pytest.param("error_foo", "error.foo", id="error"),
    pytest.param("done_state_foo", "done.state.foo", id="done_state"),
    pytest.param("done_invoke_foo", "done.invoke.foo", id="done_invoke"),
]


def declare_then_reference(s, t):
    event = Event()
    s.to(t, event=event)
    return event


def decorate(s, t):
    @s.to(t)
    def action(self):
        return "acted"

    return action


FORMS = [
    pytest.param(lambda s, t: s.to(t), id="bare"),
    pytest.param(lambda s, t: Event(s.to(t), name="Boom"), id="event"),
    pytest.param(declare_then_reference, id="referenced"),
    pytest.param(decorate, id="decorator"),
]

NESTED = [pytest.param(False, id="top-level"), pytest.param(True, id="nested")]


def build_chart(attr, declare, nested):
    """Build a chart where ``attr`` holds the declaration of ``bag_end -> green_dragon``."""
    if nested and declare is declare_then_reference:
        pytest.skip("an Event with no transitions is not supported inside a nested body")
    bag_end = State(initial=True)
    green_dragon = State(final=True)
    body = {"bag_end": bag_end, "green_dragon": green_dragon, attr: declare(bag_end, green_dragon)}
    if nested:
        body = {"shire": NestedStateFactory("shire", (State.Compound,), body)}
    return type("Hobbiton", (StateChart,), body)


def source_state(chart):
    return chart.states_map["bag_end"]


async def awaited(result):
    if isawaitable(result):
        result = await result
    return result


class TestExpandEventId:
    def test_plain_name_expands_to_itself(self):
        assert _expand_event_id("go") == ["go"]

    def test_error_prefix_dots_every_underscore(self):
        assert _expand_event_id("error_foo_bar") == ["error_foo_bar", "error.foo.bar"]

    def test_done_prefixes_keep_the_suffix(self):
        assert _expand_event_id("done_state_lonely_mountain") == [
            "done_state_lonely_mountain",
            "done.state.lonely_mountain",
        ]
        assert _expand_event_id("done_invoke_child_1") == [
            "done_invoke_child_1",
            "done.invoke.child_1",
        ]


@pytest.mark.parametrize("nested", NESTED)
@pytest.mark.parametrize("declare", FORMS)
@pytest.mark.parametrize(("attr", "dotted"), PREFIXES)
class TestExpandedIdsRegisterOneEventEach:
    def test_both_ids_are_events_of_the_chart(self, attr, dotted, declare, nested):
        chart = build_chart(attr, declare, nested)

        assert [event.id for event in chart.events] == [attr, dotted]
        assert isinstance(getattr(chart, attr), Event)
        assert getattr(chart, attr).id == attr
        assert getattr(chart, dotted).id == dotted

    def test_transition_carries_each_id_once(self, attr, dotted, declare, nested):
        chart = build_chart(attr, declare, nested)

        (transition,) = source_state(chart).transitions
        assert [event.id for event in transition.events] == [attr, dotted]

    async def test_method_call_runs_the_transition(self, attr, dotted, declare, nested, sm_runner):
        sm = await sm_runner.start(build_chart(attr, declare, nested))
        assert sm.bag_end.is_active

        await awaited(getattr(sm, attr)())

        assert sm.green_dragon.is_active

    async def test_send_dotted_id_runs_the_transition(
        self, attr, dotted, declare, nested, sm_runner
    ):
        sm = await sm_runner.start(build_chart(attr, declare, nested))

        await sm_runner.send(sm, dotted)

        assert sm.green_dragon.is_active

    async def test_allowed_and_enabled_events_list_both_ids(
        self, attr, dotted, declare, nested, sm_runner
    ):
        sm = await sm_runner.start(build_chart(attr, declare, nested))

        assert [event.id for event in sm.allowed_events] == [attr, dotted]
        enabled = await awaited(sm.enabled_events())
        assert [event.id for event in enabled] == [attr, dotted]


@pytest.mark.parametrize("nested", NESTED)
@pytest.mark.parametrize(("attr", "dotted"), PREFIXES)
class TestDeclaredArgumentsAreKeptOnEveryId:
    def test_name_and_delay(self, attr, dotted, nested):
        chart = build_chart(attr, lambda s, t: Event(s.to(t), name="Boom", delay=50), nested)

        assert [(e.id, e.name, e.delay) for e in chart.events] == [
            (attr, "Boom", 50),
            (dotted, "Boom", 50),
        ]
        assert getattr(chart, attr).name == "Boom"
        assert getattr(chart, attr).delay == 50

    def test_internal(self, attr, dotted, nested):
        chart = build_chart(attr, lambda s, t: Event(s.to(t), internal=True), nested)

        assert [(e.id, e.internal) for e in chart.events] == [(attr, True), (dotted, True)]

    def test_name_defaults_to_the_humanized_id(self, attr, dotted, nested):
        chart = build_chart(attr, lambda s, t: Event(s.to(t)), nested)

        assert [e.name for e in chart.events] == [humanize_id(attr), humanize_id(dotted)]


@pytest.mark.parametrize(
    "declare",
    [
        pytest.param(lambda t: t.from_.any(), id="bare"),
        pytest.param(lambda t: Event(t.from_.any(), name="Boom"), id="event"),
    ],
)
class TestAnyStateSource:
    """``from_.any()`` copies its transition onto every non-final state once, with every id."""

    @staticmethod
    def build(declare):
        class Hobbiton(StateChart):
            bag_end = State(initial=True)
            green_dragon = State()
            mordor = State(final=True)

            leave = bag_end.to(green_dragon)
            error_foo = declare(mordor)

        return Hobbiton

    def test_one_transition_per_state_carrying_both_ids(self, declare):
        chart = self.build(declare)

        for state in (chart.bag_end, chart.green_dragon):
            copies = [t for t in state.transitions if t.target is chart.mordor]
            assert [str(t.events) for t in copies] == ["error_foo error.foo"]

    def test_diagram_draws_each_copy_once(self, declare):
        chart = self.build(declare)

        edges = [(t.source, t.targets) for t in extract(chart).transitions]
        assert edges == [
            ("bag_end", ["green_dragon"]),
            ("bag_end", ["mordor"]),
            ("green_dragon", ["mordor"]),
        ]

    async def test_method_call_runs_from_any_state(self, declare, sm_runner):
        sm = await sm_runner.start(self.build(declare))
        await sm_runner.send(sm, "leave")

        await awaited(sm.error_foo())

        assert sm.mordor.is_active

    def test_alias_of_the_same_list_joins_the_copy(self, declare):
        class Hobbiton(StateChart):
            bag_end = State(initial=True)
            mordor = State(final=True)

            flee = declare(mordor)
            escape = flee

        assert [str(t.events) for t in Hobbiton.bag_end.transitions] == ["flee escape"]
