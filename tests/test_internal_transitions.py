"""Internal transitions (``internal=True``): which states are exited and entered.

An internal transition never exits its source when the target is a descendant of it, and an
atomic source that targets itself is neither exited nor entered. A compound or parallel source
that targets itself is exited and re-entered, as SCXML mandates. The outcome is the same on
``StateChart`` and ``StateMachine``.
"""

import json

import pytest
from statemachine.io import load

from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart
from statemachine import StateMachine


class Recorder:
    def __init__(self):
        self.log: list[str] = []

    def on_exit_state(self, state):
        self.log.append(f"exit {state.id}")

    def on_enter_state(self, state):
        self.log.append(f"enter {state.id}")

    def effect(self, event):
        self.log.append(f"effect {event}")


@pytest.fixture(params=[StateChart, StateMachine], ids=["StateChart", "StateMachine"])
def base(request):
    return request.param


async def start(sm_runner, cls, *prepare):
    recorder = Recorder()
    sm = await sm_runner.start(cls, listeners=[recorder])
    for event in prepare:
        await sm_runner.send(sm, event)
    recorder.log.clear()
    return sm, recorder


def atomic_machine(base):
    class Cart(base):
        shopping = State(initial=True)
        checkout = State(final=True)

        add_item = shopping.to.itself(internal=True, on="effect")
        pay = shopping.to(checkout)

    return Cart


def compound_machine(base):
    class Order(base):
        class open(State.Compound):
            draft = State(initial=True)
            review = State()

            submit = draft.to(review)

        closed = State(final=True)

        reset = open.to.itself(internal=True, on="effect")
        jump = open.to(open.review, internal=True, on="effect")
        close = open.to(closed)

    return Order


def parallel_machine(base):
    class Trip(base):
        class booking(State.Compound):
            idle = State(initial=True)

            class planning(State.Parallel):
                class flight(State.Compound):
                    searching = State(initial=True)
                    booked = State()

                    book_flight = searching.to(booked)

                class hotel(State.Compound):
                    browsing = State(initial=True)

        done = State(final=True)

        plan = booking.to(booking.planning, internal=True, on="effect")
        replan = booking.planning.to.itself(internal=True, on="effect")
        finish = booking.to(done)

    return Trip


def nested_atomic_machine(base):
    class Console(base):
        class session(State.Parallel):
            class editor(State.Compound):
                clean = State(initial=True)
                dirty = State()

                edit = clean.to(dirty)
                type_key = dirty.to.itself(internal=True, on="effect")

            class status(State.Compound):
                ready = State(initial=True)

        closed = State(final=True)

        quit = session.to(closed)

    return Console


def history_machine(base):
    class Wizard(base):
        class steps(State.Compound):
            first = State(initial=True)
            second = State()
            h = HistoryState()

            advance = first.to(second)

        paused = State()
        done = State(final=True)

        resume = steps.to(steps.h, internal=True, on="effect")
        pause = steps.to(paused)
        unpause = paused.to(steps.h)
        finish = steps.to(done) | paused.to(done)

    return Wizard


@pytest.mark.timeout(5)
class TestInternalTransitions:
    async def test_atomic_self_runs_only_the_effect(self, sm_runner, base):
        sm, recorder = await start(sm_runner, atomic_machine(base))

        await sm_runner.send(sm, "add_item")

        assert recorder.log == ["effect add_item"]
        assert sm.configuration_values == {"shopping"}

    async def test_local_transition_to_descendant_keeps_source_active(self, sm_runner, base):
        sm, recorder = await start(sm_runner, compound_machine(base))

        await sm_runner.send(sm, "jump")

        assert recorder.log == ["exit draft", "effect jump", "enter review"]
        assert sm.configuration_values == {"open", "review"}
        await sm_runner.send(sm, "close")
        assert sm.configuration_values == {"closed"}

    async def test_compound_self_exits_and_reenters_source(self, sm_runner, base):
        sm, recorder = await start(sm_runner, compound_machine(base), "submit")

        await sm_runner.send(sm, "reset")

        assert recorder.log == [
            "exit review",
            "exit open",
            "effect reset",
            "enter open",
            "enter draft",
        ]
        assert sm.configuration_values == {"open", "draft"}

    async def test_local_transition_to_parallel_descendant_enters_every_region(
        self, sm_runner, base
    ):
        sm, recorder = await start(sm_runner, parallel_machine(base))

        await sm_runner.send(sm, "plan")

        assert recorder.log == [
            "exit idle",
            "effect plan",
            "enter planning",
            "enter flight",
            "enter searching",
            "enter hotel",
            "enter browsing",
        ]
        assert sm.configuration_values == {
            "booking",
            "planning",
            "flight",
            "searching",
            "hotel",
            "browsing",
        }

    async def test_parallel_self_exits_and_reenters_source(self, sm_runner, base):
        sm, recorder = await start(sm_runner, parallel_machine(base), "plan", "book_flight")

        await sm_runner.send(sm, "replan")

        assert recorder.log == [
            "exit browsing",
            "exit booked",
            "exit hotel",
            "exit flight",
            "exit planning",
            "effect replan",
            "enter planning",
            "enter flight",
            "enter searching",
            "enter hotel",
            "enter browsing",
        ]
        assert sm.configuration_values == {
            "booking",
            "planning",
            "flight",
            "searching",
            "hotel",
            "browsing",
        }

    async def test_nested_atomic_self_leaves_ancestors_untouched(self, sm_runner, base):
        sm, recorder = await start(sm_runner, nested_atomic_machine(base), "edit")

        await sm_runner.send(sm, "type_key")

        assert recorder.log == ["effect type_key"]
        assert sm.configuration_values == {"session", "editor", "dirty", "status", "ready"}

    async def test_local_transition_to_recorded_history_keeps_source_active(self, sm_runner, base):
        sm, recorder = await start(sm_runner, history_machine(base), "advance", "pause", "unpause")

        await sm_runner.send(sm, "resume")

        assert recorder.log == ["exit second", "effect resume", "enter second"]
        assert sm.configuration_values == {"steps", "second"}


def test_multi_target_internal_from_an_atomic_source_is_external():
    sm = load(
        json.dumps(
            {
                "name": "Beacons",
                "states": {
                    "beacons": {
                        "parallel": True,
                        "initial": True,
                        "states": {
                            "east": {
                                "states": {
                                    "east_dark": {
                                        "initial": True,
                                        "transitions": [
                                            {
                                                "event": "light",
                                                "target": "east_dark west_lit",
                                                "internal": True,
                                            }
                                        ],
                                    }
                                }
                            },
                            "west": {
                                "states": {
                                    "west_dark": {"initial": True},
                                    "west_lit": {},
                                }
                            },
                        },
                    }
                },
            }
        ),
        format="json",
        validate=True,
    )()

    sm.send("light")

    assert sm.configuration_values == {"beacons", "east", "east_dark", "west", "west_lit"}
