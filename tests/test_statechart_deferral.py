"""Event deferral.

Tests exercise states that defer events: the events are kept instead of discarded, replayed
in order once the machine reaches a configuration that no longer defers them, and visible
through the introspection API. Deferral is inherited from ancestors and, in parallel regions,
requires every active atomic state to agree.

Theme: The Council of Elrond and the Fellowship's journey.
"""

import pickle

import pytest
from statemachine.event_data import TriggerData
from statemachine.exceptions import InvalidDefinition
from statemachine.exceptions import TransitionNotAllowed

from statemachine import State
from statemachine import StateChart
from statemachine import StateMachine


class Council(StateChart):
    gathering = State(initial=True, defer=["speak"])
    deliberating = State()
    decided = State(final=True)

    convene = gathering.to(deliberating)
    speak = deliberating.to(decided)


class Road(StateChart):
    shire = State(initial=True, defer=["ambush"])
    bree = State(defer=["ambush"])
    weathertop = State()
    rivendell = State(final=True)

    to_bree = shire.to(bree)
    to_weathertop = bree.to(weathertop)
    ambush = weathertop.to(rivendell)


class TestStateParameters:
    def test_defer_is_stored_as_frozenset(self):
        state = State(defer=["speak", "listen"])
        assert state.deferred_events == frozenset({"speak", "listen"})

    def test_nothing_is_deferred_by_default(self):
        assert State().deferred_events == frozenset()

    def test_final_state_cannot_defer(self):
        with pytest.raises(InvalidDefinition, match="final"):
            State(final=True, defer=["speak"])

    def test_recursive_includes_every_ancestor(self):
        grandparent = State(defer=["a"])
        parent = State(defer=["b", "a"])
        child = State(defer=["c"])
        parent.parent = grandparent
        child.parent = parent

        assert child.deferred_events_recursive == frozenset({"a", "b", "c"})
        assert parent.deferred_events_recursive == frozenset({"a", "b"})
        assert State().deferred_events_recursive == frozenset()


@pytest.mark.timeout(5)
class TestDeferralAndReplay:
    async def test_deferred_event_is_replayed_after_leaving_the_state(self, sm_runner):
        sm = await sm_runner.start(Council)

        await sm_runner.send(sm, "speak")
        assert "gathering" in sm.configuration_values
        assert sm.pending_deferred_event_ids == ["speak"]

        await sm_runner.send(sm, "convene")
        assert "decided" in sm.configuration_values
        assert sm.deferred_events == []

    async def test_event_stays_queued_while_the_next_state_also_defers_it(self, sm_runner):
        sm = await sm_runner.start(Road)
        await sm_runner.send(sm, "ambush")

        await sm_runner.send(sm, "to_bree")
        assert "bree" in sm.configuration_values
        assert sm.pending_deferred_event_ids == ["ambush"]

        await sm_runner.send(sm, "to_weathertop")
        assert "rivendell" in sm.configuration_values
        assert sm.deferred_events == []

    async def test_replay_keeps_the_order_the_events_were_sent(self, sm_runner):
        entered = []

        class Watch(StateChart):
            resting = State(initial=True, defer=["first_watch", "second_watch"])
            first = State()
            second = State()
            dawn = State(final=True)

            wake = resting.to(first)
            first_watch = first.to(second)
            second_watch = second.to(dawn)

            def on_enter_state(self, target):
                entered.append(target.id)

        sm = await sm_runner.start(Watch)
        await sm_runner.send(sm, "first_watch")
        await sm_runner.send(sm, "second_watch")
        assert sm.pending_deferred_event_ids == ["first_watch", "second_watch"]

        await sm_runner.send(sm, "wake")
        assert "dawn" in sm.configuration_values
        assert entered == ["resting", "first", "second", "dawn"]

    async def test_replayed_event_keeps_its_arguments(self, sm_runner):
        received = []

        class Messenger(StateChart):
            riding = State(initial=True, defer=["deliver"])
            arrived = State()
            delivered = State(final=True)

            arrive = riding.to(arrived)
            deliver = arrived.to(delivered)

            def on_deliver(self, message=None, urgent=False):
                received.append((message, urgent))

        sm = await sm_runner.start(Messenger)
        await sm_runner.send(sm, "deliver", message="the ring", urgent=True)
        await sm_runner.send(sm, "arrive")

        assert received == [("the ring", True)]

    async def test_event_with_an_enabled_transition_is_not_deferred(self, sm_runner):
        class Gate(StateChart):
            closed = State(initial=True, defer=["knock"])
            open = State(final=True)

            knock = closed.to(open)

        sm = await sm_runner.start(Gate)
        await sm_runner.send(sm, "knock")

        assert "open" in sm.configuration_values
        assert sm.deferred_events == []

    async def test_events_not_listed_in_defer_are_not_queued(self, sm_runner):
        sm = await sm_runner.start(Council)
        await sm_runner.send(sm, "unknown")

        assert sm.deferred_events == []

    async def test_deferral_does_not_require_a_declared_event(self, sm_runner):
        class Lookout(StateChart):
            watching = State(initial=True, defer=["not_declared"])
            relieved = State(final=True)

            relieve = watching.to(relieved)

        sm = await sm_runner.start(Lookout)
        await sm_runner.send(sm, "not_declared")

        assert sm.pending_deferred_event_ids == ["not_declared"]

    async def test_queue_is_cleared_when_the_machine_terminates(self, sm_runner):
        class Hobbit(StateChart):
            hiding = State(initial=True, defer=["call"])
            gone = State(final=True)

            leave = hiding.to(gone)

        sm = await sm_runner.start(Hobbit)
        await sm_runner.send(sm, "call")
        assert len(sm.deferred_events) == 1

        await sm_runner.send(sm, "leave")
        assert sm.is_terminated
        assert sm.deferred_events == []


@pytest.mark.timeout(5)
class TestDeferralPrecedence:
    async def test_deferral_wins_over_allow_event_without_transition(self, sm_runner):
        class Tolerant(Council):
            allow_event_without_transition = True

        sm = await sm_runner.start(Tolerant)
        await sm_runner.send(sm, "speak")
        assert sm.pending_deferred_event_ids == ["speak"]

        await sm_runner.send(sm, "convene")
        assert "decided" in sm.configuration_values

    async def test_deferral_wins_over_transition_not_allowed(self, sm_runner):
        class Strict(StateMachine):
            allow_event_without_transition = False

            gathering = State(initial=True, defer=["speak"])
            deliberating = State()
            decided = State(final=True)

            convene = gathering.to(deliberating)
            speak = deliberating.to(decided)

        sm = await sm_runner.start(Strict)
        await sm_runner.send(sm, "speak")
        assert sm.pending_deferred_event_ids == ["speak"]

        await sm_runner.send(sm, "convene")
        assert "decided" in sm.configuration_values

    async def test_other_events_are_still_rejected(self, sm_runner):
        class Strict(StateMachine):
            allow_event_without_transition = False

            gathering = State(initial=True, defer=["speak"])
            decided = State(final=True)

            finish = gathering.to(decided)

        sm = await sm_runner.start(Strict)
        with pytest.raises(TransitionNotAllowed):
            await sm_runner.send(sm, "unknown")
        assert sm.deferred_events == []


@pytest.mark.timeout(5)
class TestDeferralInHierarchy:
    async def test_children_inherit_the_deferral_of_a_compound_state(self, sm_runner):
        class Journey(StateChart):
            class mordor(State.Compound, defer=["rest"]):
                gates = State(initial=True)
                mount_doom = State()

                climb = gates.to(mount_doom)

            shire = State()
            done = State(final=True)

            return_home = mordor.to(shire)
            rest = shire.to(done)

        sm = await sm_runner.start(Journey)
        await sm_runner.send(sm, "rest")
        await sm_runner.send(sm, "climb")
        assert sm.pending_deferred_event_ids == ["rest"]

        await sm_runner.send(sm, "return_home")
        assert "done" in sm.configuration_values

    async def test_parallel_regions_must_all_defer_the_event(self, sm_runner):
        class Fellowship(StateChart):
            class company(State.Parallel):
                class ringbearer(State.Compound):
                    walking = State(initial=True, defer=["rest"])

                class guard(State.Compound):
                    watching = State(initial=True)

            camp = State(final=True)

            make_camp = company.to(camp)

        sm = await sm_runner.start(Fellowship)
        assert not sm.is_event_deferred("rest")

        await sm_runner.send(sm, "rest")
        assert sm.deferred_events == []

    async def test_parallel_regions_that_all_defer_the_event_queue_it(self, sm_runner):
        class Fellowship(StateChart):
            class company(State.Parallel):
                class ringbearer(State.Compound):
                    walking = State(initial=True, defer=["rest"])

                class guard(State.Compound):
                    watching = State(initial=True, defer=["rest"])

            camp = State()
            asleep = State(final=True)

            make_camp = company.to(camp)
            rest = camp.to(asleep)

        sm = await sm_runner.start(Fellowship)
        await sm_runner.send(sm, "rest")
        assert sm.pending_deferred_event_ids == ["rest"]

        await sm_runner.send(sm, "make_camp")
        assert "asleep" in sm.configuration_values


@pytest.mark.timeout(5)
class TestIntrospection:
    async def test_is_event_deferred_follows_the_configuration(self, sm_runner):
        sm = await sm_runner.start(Council)
        assert sm.is_event_deferred("speak")
        assert not sm.is_event_deferred("convene")

        await sm_runner.send(sm, "convene")
        assert not sm.is_event_deferred("speak")

    async def test_deferred_events_returns_a_copy_of_trigger_data(self, sm_runner):
        sm = await sm_runner.start(Council)
        await sm_runner.send(sm, "speak")

        events = sm.deferred_events
        assert [type(item) for item in events] == [TriggerData]
        assert events[0].event == "speak"

        events.clear()
        assert len(sm.deferred_events) == 1

    async def test_pending_ids_are_listed_in_fifo_order(self, sm_runner):
        class Watch(StateChart):
            resting = State(initial=True, defer=["a", "b"])
            moving = State(final=True)

            go = resting.to(moving)

        sm = await sm_runner.start(Watch)
        assert sm.pending_deferred_event_ids == []

        await sm_runner.send(sm, "b")
        await sm_runner.send(sm, "a")
        assert sm.pending_deferred_event_ids == ["b", "a"]

    async def test_cleared_events_are_not_replayed(self, sm_runner):
        sm = await sm_runner.start(Council)
        await sm_runner.send(sm, "speak")

        sm.clear_deferred_queue()
        assert sm.deferred_events == []

        await sm_runner.send(sm, "convene")
        assert "deliberating" in sm.configuration_values

    def test_pickle_does_not_carry_the_queue(self):
        sm = Council()
        sm.send("speak")
        assert len(sm.deferred_events) == 1

        restored = pickle.loads(pickle.dumps(sm))
        assert restored.deferred_events == []
        assert "gathering" in restored.configuration_values


@pytest.mark.timeout(5)
class TestCallbacks:
    async def test_inline_callbacks(self, sm_runner):
        calls = []

        def deferred(event, state, source, target, machine, model):
            calls.append(("defer", str(event), state.id, source.id, target))
            assert machine is sm
            assert model is sm.model

        def replayed(event, state):
            calls.append(("replay", str(event), state.id))

        class Messenger(StateChart):
            riding = State(initial=True, defer=["deliver"], on_defer=deferred)
            arrived = State(on_replay=replayed)
            delivered = State(final=True)

            arrive = riding.to(arrived)
            deliver = arrived.to(delivered)

        sm = await sm_runner.start(Messenger)
        await sm_runner.send(sm, "deliver")
        await sm_runner.send(sm, "arrive")

        assert calls == [
            ("defer", "deliver", "riding", "riding", None),
            ("replay", "deliver", "arrived"),
        ]

    async def test_naming_conventions(self, sm_runner):
        calls = []

        class Messenger(StateChart):
            riding = State(initial=True, defer=["deliver"])
            arrived = State()
            delivered = State(final=True)

            arrive = riding.to(arrived)
            deliver = arrived.to(delivered)

            def on_defer_event(self, event):
                calls.append(f"defer_event {event}")

            def on_defer_riding(self, event):
                calls.append(f"defer_riding {event}")

            def on_replay_event(self, event):
                calls.append(f"replay_event {event}")

            def on_replay_arrived(self, event):
                calls.append(f"replay_arrived {event}")

        sm = await sm_runner.start(Messenger)
        await sm_runner.send(sm, "deliver")
        await sm_runner.send(sm, "arrive")

        assert calls == [
            "defer_event deliver",
            "defer_riding deliver",
            "replay_event deliver",
            "replay_arrived deliver",
        ]


@pytest.mark.timeout(5)
class TestAsyncCallbacks:
    async def test_coroutine_callbacks_are_awaited(self):
        calls = []

        async def deferred(**kwargs):
            calls.append("defer")

        async def replayed(**kwargs):
            calls.append("replay")

        class Messenger(StateChart):
            riding = State(initial=True, defer=["deliver"], on_defer=deferred)
            arrived = State(on_replay=replayed)
            delivered = State(final=True)

            arrive = riding.to(arrived)
            deliver = arrived.to(delivered)

        sm = Messenger()
        await sm.activate_initial_state()
        await sm.send("deliver")
        await sm.send("arrive")

        assert calls == ["defer", "replay"]
        assert "delivered" in sm.configuration_values


class TestValidation:
    def test_unknown_deferred_event_is_ignored_by_default(self):
        class Lookout(StateChart):
            watching = State(initial=True, defer=["not_declared"])
            relieved = State(final=True)

            relieve = watching.to(relieved)

        assert Lookout().is_event_deferred("not_declared")

    def test_unknown_deferred_event_is_rejected_when_validating(self):
        with pytest.raises(InvalidDefinition, match="unknown event"):

            class Lookout(StateChart):
                validate_deferred_events = True

                watching = State(initial=True, defer=["not_declared"])
                relieved = State(final=True)

                relieve = watching.to(relieved)

    def test_nested_states_are_validated_too(self):
        with pytest.raises(InvalidDefinition, match="unknown event"):

            class Journey(StateChart):
                validate_deferred_events = True

                class mordor(State.Compound, defer=["not_declared"]):
                    gates = State(initial=True)

                done = State(final=True)

                leave = mordor.to(done)

    def test_declared_events_pass_validation(self):
        class Lookout(StateChart):
            validate_deferred_events = True

            watching = State(initial=True, defer=["relieve"])
            relieved = State(final=True)

            relieve = watching.to(relieved)

        assert Lookout().is_event_deferred("relieve")
