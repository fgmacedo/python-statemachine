"""Tests for future-based result routing in the async engine.

When multiple coroutines send events concurrently, only one acquires the
processing lock. The others must still receive their own event's result (or
exception) via an ``asyncio.Future`` attached to each ``TriggerData``.

See: https://github.com/fgmacedo/python-statemachine/issues/509
"""

import asyncio

import pytest
from statemachine.engines.base import EventQueue
from statemachine.event_data import TriggerData
from statemachine.exceptions import StateMachineError
from statemachine.exceptions import TransitionNotAllowed

from statemachine import Event
from statemachine import State
from statemachine import StateChart
from statemachine import StateMachine

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class TrafficLight(StateChart):
    green = State(initial=True)
    yellow = State()
    red = State()

    slow_down = green.to(yellow)
    stop = yellow.to(red)
    go = red.to(green)

    async def on_slow_down(self):
        return "slowing"

    async def on_stop(self):
        return "stopped"

    async def on_go(self):
        return "going"


class FailingMachine(StateChart):
    s1 = State(initial=True)
    s2 = State()
    s3 = State(final=True)

    ok = s1.to(s2)
    fail = s2.to(s3)

    async def on_ok(self):
        return "ok_result"

    async def on_fail(self):
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConcurrentSendsGetCorrectResults:
    """asyncio.gather(sm.send("a"), sm.send("b")) — each caller gets its own result."""

    @pytest.mark.asyncio()
    async def test_sequential_sends(self):
        """Baseline: sequential sends return correct results."""
        sm = TrafficLight()
        await sm.activate_initial_state()

        r1 = await sm.send("slow_down")
        assert r1 == "slowing"

        r2 = await sm.send("stop")
        assert r2 == "stopped"

    @pytest.mark.asyncio()
    async def test_single_async_caller_gets_result(self):
        """Single async caller gets its callback result (backward compat)."""
        sm = TrafficLight()
        await sm.activate_initial_state()

        result = await sm.slow_down()
        assert result == "slowing"


class TestExceptionRouting:
    """Exceptions from one event must be routed to the correct caller."""

    @pytest.mark.asyncio()
    async def test_exception_reaches_caller(self):
        """When catch_errors_as_events=False (not default for StateChart), the
        exception propagates to the caller of that event."""

        class FailingSC(StateChart):
            catch_errors_as_events = False
            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

            async def on_go(self):
                raise ValueError("broken")

        sm = FailingSC()
        await sm.activate_initial_state()

        with pytest.raises(ValueError, match="broken"):
            await sm.send("go")


class TestTransitionNotAllowedRouting:
    """TransitionNotAllowed from an unknown event reaches the correct caller."""

    @pytest.mark.asyncio()
    async def test_transition_not_allowed(self):
        class StrictSC(StateChart):
            allow_event_without_transition = False
            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

            async def on_go(self):
                return "went"

        sm = StrictSC()
        await sm.activate_initial_state()

        # "go" works
        result = await sm.send("go")
        assert result == "went"

        # Now in s2, "go" has no transition
        with pytest.raises(sm.TransitionNotAllowed):
            await sm.send("go")


class TestFutureEdgeCases:
    """Edge cases for future-based routing."""

    @pytest.mark.asyncio()
    async def test_initial_activation_no_future(self):
        """activate_initial_state has no caller_trigger, should work fine."""
        sm = TrafficLight()
        await sm.activate_initial_state()
        assert "green" in sm.configuration_values

    @pytest.mark.asyncio()
    async def test_allow_event_without_transition_resolves_none(self):
        """When allow_event_without_transition=True and no transition matches,
        the caller should get None (not hang)."""
        sm = TrafficLight()
        await sm.activate_initial_state()

        # "stop" is not valid from "green", but allow_event_without_transition=True
        result = await sm.send("stop")
        assert result is None

    @pytest.mark.asyncio()
    async def test_concurrent_sends_via_gather(self):
        """Two coroutines sending events concurrently via asyncio.gather.

        One coroutine will hold the lock; the other awaits its future.
        Both should get their own results.
        """

        class SlowMachine(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State(final=True)

            step1 = s1.to(s2)
            step2 = s2.to(s3)

            async def on_step1(self):
                # Yield control so the second coroutine can enqueue its event
                await asyncio.sleep(0)
                return "result_1"

            async def on_step2(self):
                return "result_2"

        sm = SlowMachine()
        await sm.activate_initial_state()

        r1, r2 = await asyncio.gather(
            sm.send("step1"),
            sm.send("step2"),
        )

        assert r1 == "result_1"
        assert r2 == "result_2"

    @pytest.mark.asyncio()
    async def test_concurrent_sends_exception_with_catch_errors_as_events_off(self):
        """When catch_errors_as_events=False and one event raises, the exception
        is routed to that caller's future; the other caller is unaffected.

        With catch_errors_as_events=False, the exception propagates and the
        processing loop clears the external queue, so the second event is
        never processed.
        """

        class ConcurrentFailMachine(StateChart):
            catch_errors_as_events = False
            s1 = State(initial=True)
            s2 = State()
            s3 = State(final=True)

            step1 = s1.to(s2)
            step2 = s2.to(s3)

            async def on_step1(self):
                await asyncio.sleep(0)
                raise RuntimeError("step1 failed")

            async def on_step2(self):
                return "step2_ok"

        sm = ConcurrentFailMachine()
        await sm.activate_initial_state()

        # step1 raises — the exception should reach step1's caller via its future.
        # step2 was queued but the processing loop rejects all pending futures
        # and clears the queue on exception.
        r1, r2 = await asyncio.gather(
            sm.send("step1"),
            sm.send("step2"),
            return_exceptions=True,
        )

        # step1's caller gets the RuntimeError
        assert isinstance(r1, RuntimeError)
        assert str(r1) == "step1 failed"
        # step2 also gets the RuntimeError (pending future rejected with same exception)
        assert isinstance(r2, RuntimeError)
        assert str(r2) == "step1 failed"

    @pytest.mark.asyncio()
    async def test_separate_tasks_with_slow_callback(self):
        """Reproduces the scenario from issue #509: two separate asyncio tasks
        send events to the same state machine. The first callback does a slow
        ``await asyncio.sleep()``, yielding control so the second task can
        enqueue its event. Both tasks must receive their own results.

        This specifically tests that concurrent external tasks (as opposed to
        reentrant calls from within callbacks) correctly get futures and don't
        return ``None``.
        """

        class SlowSC(StateChart):
            s1 = State(initial=True)
            s2 = State()

            noop = s1.to(s2)
            noop2 = s2.to.itself()

            async def on_noop(self, name):
                await asyncio.sleep(0.01)
                return f"noop done by {name}"

            async def on_noop2(self, name):
                return f"noop2 done by {name}"

        sm = SlowSC()
        await sm.activate_initial_state()

        results = {}

        async def fn1():
            results["fn1"] = await sm.send("noop", "fn1")

        async def fn2():
            # Small delay so fn1 acquires the lock first
            await asyncio.sleep(0.005)
            results["fn2"] = await sm.send("noop2", "fn2")

        await asyncio.gather(fn1(), fn2())

        assert results["fn1"] == "noop done by fn1"
        assert results["fn2"] == "noop2 done by fn2"

    @pytest.mark.asyncio()
    async def test_separate_tasks_validator_exception_routing(self):
        """Issue #509 scenario: validator exception must reach the correct
        caller task, not the task that holds the processing lock.
        """

        class ValidatorSC(StateChart):
            catch_errors_as_events = False
            s1 = State(initial=True)
            s2 = State()

            noop = s1.to(s2)
            noop2 = s2.to.itself(validators="check_allowed")

            async def on_noop(self):
                await asyncio.sleep(0.01)
                return "noop ok"

            def check_allowed(self):
                raise ValueError("noop2 is not allowed")

        sm = ValidatorSC()
        await sm.activate_initial_state()

        results = {}
        errors = {}

        async def fn1():
            results["fn1"] = await sm.send("noop")

        async def fn2():
            await asyncio.sleep(0.005)
            try:
                await sm.send("noop2")
            except ValueError as e:
                errors["fn2"] = e

        await asyncio.gather(fn1(), fn2())

        assert results["fn1"] == "noop ok"
        assert "fn2" in errors
        assert str(errors["fn2"]) == "noop2 is not allowed"


def mount_doom_quest(base):
    class MountDoom(base):
        road = State(initial=True)
        orodruin = State()
        destroyed = State(final=True)

        climb = road.to(orodruin) | orodruin.to.itself()
        cast_ring = road.to(destroyed) | orodruin.to(destroyed)

        def __init__(self, *args, **kwargs):
            self.ring_falls = asyncio.Event()
            super().__init__(*args, **kwargs)

        async def on_cast_ring(self):
            await self.ring_falls.wait()
            return "destroyed"

    return MountDoom


def shire_journey(base):
    class Shire(base):
        bag_end = State(initial=True)
        rivendell = State()
        grey_havens = State(final=True)

        journey = bag_end.to(rivendell)
        long_journey = Event(bag_end.to(rivendell), delay=60000)
        sail = bag_end.to(grey_havens, on="say_goodbye") | rivendell.to(grey_havens)

        def __init__(self, *args, **kwargs):
            self.journeys = 0
            super().__init__(*args, **kwargs)

        def say_goodbye(self):
            self.journey.put()
            self.long_journey.put()

        def on_enter_rivendell(self):
            self.journeys += 1

    return Shire


async def start_casting_the_ring(sm):
    """Start ``cast_ring`` in a task that holds the processing lock until ``ring_falls``."""
    await sm.activate_initial_state()
    holder = asyncio.ensure_future(sm.send("cast_ring"))
    await asyncio.sleep(0)
    return holder


async def queue_behind(sm, *sends):
    waiters = [asyncio.ensure_future(sm.send(event, **kwargs)) for event, kwargs in sends]
    await asyncio.sleep(0)
    return waiters


class TestEventsDroppedAtFinalState:
    """Events still queued when the machine reaches a top-level final state are not run,
    and a coroutine awaiting one gets what a terminated machine answers to a new event.

    See: https://github.com/fgmacedo/python-statemachine/issues/678
    """

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_statechart_callers_get_none(self):
        sm = mount_doom_quest(StateChart)()
        holder = await start_casting_the_ring(sm)
        waiters = await queue_behind(sm, ("climb", {}), ("climb", {}), ("climb", {"delay": 60000}))

        sm.ring_falls.set()

        assert await holder == "destroyed"
        assert await asyncio.gather(*waiters) == [None, None, None]
        assert sm.configuration_values == {"destroyed"}

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_statemachine_callers_get_transition_not_allowed(self):
        sm = mount_doom_quest(StateMachine)()
        holder = await start_casting_the_ring(sm)
        waiters = await queue_behind(sm, ("climb", {}), ("climb", {}), ("climb", {"delay": 60000}))

        sm.ring_falls.set()

        assert await holder == "destroyed"
        results = await asyncio.gather(*waiters, return_exceptions=True)
        assert all(isinstance(result, TransitionNotAllowed) for result in results)
        assert [result.event.id for result in results] == ["climb", "climb", "climb"]
        assert sm.configuration_values == {"destroyed"}

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_each_caller_gets_its_own_event(self):
        sm = mount_doom_quest(StateMachine)()
        holder = await start_casting_the_ring(sm)
        waiters = await queue_behind(sm, ("climb", {}), ("cast_ring", {}))

        sm.ring_falls.set()

        assert await holder == "destroyed"
        results = await asyncio.gather(*waiters, return_exceptions=True)
        assert [result.event.id for result in results] == ["climb", "cast_ring"]

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_cancelled_caller_does_not_stop_the_others(self):
        sm = mount_doom_quest(StateChart)()
        holder = await start_casting_the_ring(sm)
        gives_up, *waiters = await queue_behind(
            sm, ("climb", {}), ("climb", {}), ("climb", {"delay": 60000})
        )
        gives_up.cancel()
        await asyncio.sleep(0)

        sm.ring_falls.set()

        assert await holder == "destroyed"
        assert await asyncio.gather(*waiters) == [None, None]
        assert gives_up.cancelled()

    @pytest.mark.timeout(5)
    @pytest.mark.parametrize("base", [StateChart, StateMachine])
    async def test_events_queued_behind_final_state_leave_no_trigger(self, sm_runner, base):
        Shire = shire_journey(base)
        sm = await sm_runner.start(Shire)
        await sm_runner.send(sm, "sail")

        assert sm.configuration_values == {"grey_havens"}
        assert sm.journeys == 0
        assert sm._engine.external_queue.is_empty()

    @pytest.mark.timeout(5)
    async def test_statechart_send_after_final_state_leaves_no_trigger(self, sm_runner):
        sm = await sm_runner.start(shire_journey(StateChart))
        await sm_runner.send(sm, "sail")

        assert await sm_runner.send(sm, "journey") is None
        assert await sm_runner.send(sm, "journey", delay=60000) is None
        assert sm.journeys == 0
        assert sm._engine.external_queue.is_empty()

    @pytest.mark.timeout(5)
    @pytest.mark.parametrize("base", [StateChart, StateMachine])
    async def test_events_queued_behind_root_parallel_completion_are_dropped(
        self, sm_runner, base
    ):
        class LastAlliance(base):
            class war(State.Parallel):
                class mordor(State.Compound):
                    besieged = State(initial=True)
                    fallen = State(final=True)
                    victory = besieged.to(fallen)

                class barad_dur(State.Compound):
                    standing = State(initial=True)
                    ruined = State(final=True)
                    victory = standing.to(ruined)

            rally = war.to.itself()

            def __init__(self, *args, **kwargs):
                self.rallies = 0
                super().__init__(*args, **kwargs)

            def on_victory(self):
                self.rally.put()

            def on_rally(self):
                self.rallies += 1

        sm = await sm_runner.start(LastAlliance)
        await sm_runner.send(sm, "victory")

        assert sm.is_terminated
        assert sm.rallies == 0
        assert sm._engine.external_queue.is_empty()

    @pytest.mark.timeout(5)
    @pytest.mark.parametrize("base", [StateChart, StateMachine])
    async def test_events_queued_behind_an_eventless_final_transition_are_dropped(
        self, sm_runner, base
    ):
        class Fellowship(base):
            rivendell = State(initial=True)
            moria = State()
            lothlorien = State(final=True)

            enter_moria = rivendell.to(moria, on="hear_drums")
            moria.to(lothlorien)
            rest = rivendell.to(lothlorien)

            def __init__(self, *args, **kwargs):
                self.rests = 0
                super().__init__(*args, **kwargs)

            def hear_drums(self):
                self.rest.put()

            def on_rest(self):
                self.rests += 1

        sm = await sm_runner.start(Fellowship)
        await sm_runner.send(sm, "enter_moria")

        assert sm.configuration_values == {"lothlorien"}
        assert sm.rests == 0
        assert sm._engine.external_queue.is_empty()


FAILING_CALLBACKS = [
    "balrog_stirs",
    "before_falling",
    "on_exit_bridge",
    "on_falling",
    "on_enter_abyss",
    "after_falling",
]


class Balrog:
    failing: "str | None" = None
    eventless = False

    def __init__(self, *args, **kwargs):
        self.flights = 0
        self.echoes = 0
        self.balrog_awake = False
        super().__init__(*args, **kwargs)

    def on_cross(self, awake=True, queued=()):
        self.balrog_awake = awake
        if not self.eventless:
            self.fall.put()
        self.echo.put()
        for event in queued:
            getattr(self, event).put()
        return "crossed"

    def on_flee(self):
        self.flights += 1
        return self.flights

    def on_echo(self):
        self.echoes += 1

    def balrog_stirs(self):
        self._maybe_fail("balrog_stirs")
        return self.balrog_awake

    def _maybe_fail(self, name):
        if name == self.failing and self.balrog_awake:
            self.balrog_awake = False
            raise ValueError(f"{name} failed")

    def validate_falling(self):
        self._maybe_fail("validate_falling")

    def before_falling(self):
        self._maybe_fail("before_falling")

    def on_exit_bridge(self):
        self._maybe_fail("on_exit_bridge")

    def on_falling(self):
        self._maybe_fail("on_falling")

    def on_enter_abyss(self):
        self._maybe_fail("on_enter_abyss")

    def after_falling(self):
        self._maybe_fail("after_falling")


def khazad_dum(base, failing=None, eventless=False):
    """``cross`` takes the bridge and, through an internal event or an eventless transition,
    the machine falls into the abyss while the balrog is awake, raising from ``failing``."""
    fall_callbacks = {
        "cond": "balrog_stirs",
        "validators": "validate_falling",
        "before": "before_falling",
        "on": "on_falling",
        "after": "after_falling",
    }

    class KhazadDum(Balrog, base):
        hall = State(initial=True)
        bridge = State()
        abyss = State()

        cross = hall.to(bridge)
        retreat = bridge.to(hall)
        if eventless:
            bridge.to(abyss, **fall_callbacks)
        else:
            fall = Event(bridge.to(abyss, **fall_callbacks), internal=True)
        flee = (
            hall.to.itself(internal=True)
            | bridge.to.itself(internal=True)
            | abyss.to.itself(internal=True)
        )
        echo = Event(
            bridge.to.itself(internal=True) | abyss.to.itself(internal=True), internal=True
        )

    KhazadDum.failing = failing
    KhazadDum.eventless = eventless
    return KhazadDum


def gated(cls):
    """Hold the processing lock when leaving the hall until ``gate`` is set."""

    class Gated(cls):
        def __init__(self, *args, **kwargs):
            self.gate = asyncio.Event()
            super().__init__(*args, **kwargs)

        async def on_exit_hall(self):
            await self.gate.wait()

    return Gated


async def cross_with_callers_queued(sm, *sends, awake=True):
    await sm.activate_initial_state()
    holder = asyncio.ensure_future(sm.send("cross", awake=awake))
    await asyncio.sleep(0)
    waiters = await queue_behind(sm, *sends)
    sm.gate.set()
    return holder, waiters


THREE_FLIGHTS: "list[tuple[str, dict]]" = [("flee", {})] * 3


class TestMacrostepErrorAnswersQueuedCallers:
    """An exception escaping the internal events or eventless transitions that follow an
    external event, like one escaping the event itself, drops the events still queued, and a
    coroutine awaiting one gets that exception.

    See: https://github.com/fgmacedo/python-statemachine/issues/686
    """

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    @pytest.mark.parametrize("eventless", [False, True], ids=["internal", "eventless"])
    @pytest.mark.parametrize("failing", FAILING_CALLBACKS)
    async def test_statemachine_callers_get_the_exception(self, failing, eventless):
        sm = gated(khazad_dum(StateMachine, failing, eventless))()
        holder, waiters = await cross_with_callers_queued(sm, *THREE_FLIGHTS)

        with pytest.raises(ValueError, match=f"{failing} failed"):
            await holder
        results = await asyncio.gather(*waiters, return_exceptions=True)
        assert [str(result) for result in results] == [f"{failing} failed"] * 3
        assert sm.flights == 0
        assert sm.echoes == 0
        assert sm._engine.external_queue.is_empty()
        assert sm._engine.internal_queue.is_empty()

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    @pytest.mark.parametrize("eventless", [False, True], ids=["internal", "eventless"])
    @pytest.mark.parametrize("failing", FAILING_CALLBACKS)
    async def test_statechart_callers_get_their_results(self, failing, eventless):
        sm = gated(khazad_dum(StateChart, failing, eventless))()
        holder, waiters = await cross_with_callers_queued(sm, *THREE_FLIGHTS)

        assert await holder == "crossed"
        assert await asyncio.gather(*waiters) == [1, 2, 3]
        assert sm.echoes == 1

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_machine_takes_new_events_afterwards(self):
        sm = gated(khazad_dum(StateMachine, "on_falling"))()
        holder, waiters = await cross_with_callers_queued(sm, *THREE_FLIGHTS)
        await asyncio.gather(holder, *waiters, return_exceptions=True)

        assert await sm.send("flee") == 1
        assert sm.configuration_values == {"bridge"}
        assert sm.echoes == 0

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_delayed_and_cancelled_callers_are_answered(self):
        sm = gated(khazad_dum(StateMachine, "on_falling"))()
        holder, (delayed, cancelled, flight) = await cross_with_callers_queued(
            sm,
            ("flee", {"delay": 60000}),
            ("flee", {"delay": 60000, "send_id": "horn"}),
            ("flee", {}),
        )
        sm.cancel_event("horn")

        results = await asyncio.gather(holder, delayed, cancelled, flight, return_exceptions=True)
        assert [str(result) for result in results] == [
            "on_falling failed",
            "on_falling failed",
            "None",
            "on_falling failed",
        ]
        assert sm.flights == 0
        assert sm._engine.external_queue.is_empty()

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_failure_after_a_queued_event_answers_its_caller_and_those_behind_it(self):
        sm = gated(khazad_dum(StateMachine, "on_falling"))()
        holder, waiters = await cross_with_callers_queued(
            sm, ("flee", {}), ("retreat", {}), ("cross", {}), *THREE_FLIGHTS[:2], awake=False
        )

        assert await holder == "crossed"
        results = await asyncio.gather(*waiters, return_exceptions=True)
        assert results[:2] == [1, None]
        assert [str(result) for result in results[2:]] == ["on_falling failed"] * 3
        assert sm.flights == 1

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_statechart_validator_failure_answers_the_callers(self):
        sm = gated(khazad_dum(StateChart, "validate_falling"))()
        holder, waiters = await cross_with_callers_queued(sm, *THREE_FLIGHTS)

        results = await asyncio.gather(holder, *waiters, return_exceptions=True)
        assert [str(result) for result in results] == ["validate_falling failed"] * 4
        assert sm.flights == 0

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_failed_initial_activation_answers_the_callers(self):
        class Gate(StateMachine):
            closed = State(initial=True)
            opened = State(final=True)

            open = closed.to(opened)

            def __init__(self):
                self.attempts = 0
                super().__init__()

            async def on_enter_closed(self):
                self.attempts += 1
                if self.attempts == 1:
                    raise ValueError("stuck")

        sm = Gate()
        results = await asyncio.gather(sm.send("open"), sm.send("open"), return_exceptions=True)

        assert [str(result) for result in results] == ["stuck", "stuck"]
        assert sm._engine.external_queue.is_empty()
        await sm.activate_initial_state()
        await sm.send("open")
        assert sm.configuration_values == {"opened"}

    @pytest.mark.timeout(5)
    async def test_internal_events_raised_before_an_external_failure_are_dropped(self, sm_runner):
        class Beacon(StateMachine):
            dark = State(initial=True)
            lit = State(final=True)

            light = dark.to(lit)
            ping = Event(dark.to.itself(internal=True), internal=True)
            wait = dark.to.itself(internal=True)

            def __init__(self, *args, **kwargs):
                self.pings = 0
                super().__init__(*args, **kwargs)

            def on_light(self):
                self.ping.put()
                raise ValueError("no fuel")

            def on_ping(self):
                self.pings += 1

        sm = await sm_runner.start(Beacon)
        with pytest.raises(ValueError, match="no fuel"):
            await sm_runner.send(sm, "light")
        await sm_runner.send(sm, "wait")

        assert sm.pings == 0
        assert sm.configuration_values == {"dark"}

    @pytest.mark.timeout(5)
    @pytest.mark.parametrize("eventless", [False, True], ids=["internal", "eventless"])
    @pytest.mark.parametrize("failing", FAILING_CALLBACKS)
    def test_sync_engine_drops_the_events_queued_behind_the_failure(self, failing, eventless):
        sm = khazad_dum(StateMachine, failing, eventless)()

        with pytest.raises(ValueError, match=f"{failing} failed"):
            sm.send("cross", queued=("flee", "flee"))

        assert sm.flights == 0
        assert sm.echoes == 0
        assert sm._engine.external_queue.is_empty()
        assert sm._engine.internal_queue.is_empty()
        assert sm.send("flee") == 1


class FlickeringLamp(StateMachine):
    """Its initial state raises an internal event whose transition fails."""

    off = State(initial=True)
    lit = State(final=True)

    switch = off.to(lit)
    flicker = Event(off.to.itself(internal=True), internal=True)

    async def on_enter_off(self):
        self.flicker.put()

    def on_flicker(self):
        raise ValueError("short circuit")


async def cancel_and_wait(task):
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


class TestMacrostepErrorReachesTheCallerOfItsEvent:
    """An exception escaping the internal events or eventless transitions that follow an
    external event reaches the caller of that event, on both engines. When no caller awaits
    that event, because a callback sent it, the exception reaches the caller running the loop.

    See: https://github.com/fgmacedo/python-statemachine/issues/689
    """

    @pytest.mark.timeout(5)
    @pytest.mark.parametrize("eventless", [False, True], ids=["internal", "eventless"])
    @pytest.mark.parametrize("failing", FAILING_CALLBACKS)
    async def test_caller_gets_the_exception(self, sm_runner, failing, eventless):
        sm = await sm_runner.start(khazad_dum(StateMachine, failing, eventless))

        with pytest.raises(ValueError, match=f"{failing} failed"):
            await sm_runner.send(sm, "cross")

        assert await sm_runner.send(sm, "flee") == 1

    @pytest.mark.timeout(5)
    async def test_statechart_caller_gets_its_result(self, sm_runner):
        sm = await sm_runner.start(khazad_dum(StateChart, "on_falling"))

        assert await sm_runner.send(sm, "cross") == "crossed"

    @pytest.mark.timeout(5)
    async def test_event_sent_by_a_callback_fails_on_the_caller_running_the_loop(self, sm_runner):
        sm = await sm_runner.start(khazad_dum(StateMachine, "on_falling"))

        with pytest.raises(ValueError, match="on_falling failed"):
            await sm_runner.send(sm, "cross", awake=False, queued=("retreat", "cross"))

        assert sm.configuration_values == {"bridge"}

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_failure_of_a_cancelled_callers_event_reaches_the_caller_running_the_loop(
        self,
    ):
        sm = gated(khazad_dum(StateMachine, "on_falling"))()
        holder, (retreat, gives_up, flee) = await cross_with_callers_queued(
            sm, ("retreat", {}), ("cross", {}), ("flee", {}), awake=False
        )
        await cancel_and_wait(gives_up)

        with pytest.raises(ValueError, match="on_falling failed"):
            await holder
        assert await retreat is None
        with pytest.raises(ValueError, match="on_falling failed"):
            await flee

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_failure_after_the_lazy_initial_activation_reaches_every_caller(self):
        sm = FlickeringLamp()
        results = await asyncio.gather(
            sm.send("switch"), sm.send("switch"), return_exceptions=True
        )

        assert [str(result) for result in results] == ["short circuit", "short circuit"]
        assert sm.configuration_values == {"off"}

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_caller_running_the_loop_retrieves_its_rejected_future(self):
        sm = FlickeringLamp()
        trigger = sm.switch.put()

        with pytest.raises(ValueError, match="short circuit"):
            await sm._processing_loop(trigger.future)
        assert not trigger.future._log_traceback


def stalled_road(base=StateMachine):
    """``go`` and ``stall`` hold the processing lock until cancelled, ``go`` until ``gate``
    is set first; ``step`` counts the steps taken."""

    class StalledRoad(base):
        start = State(initial=True)
        road = State()

        go = start.to(road)
        stall = start.to.itself(internal=True) | road.to.itself(internal=True)
        step = start.to.itself(internal=True) | road.to.itself(internal=True)
        hop = Event(road.to.itself(internal=True), internal=True)

        def __init__(self, *args, **kwargs):
            self.gate = asyncio.Event()
            self.stalling = asyncio.Event()
            self.steps = 0
            self.hops = 0
            super().__init__(*args, **kwargs)

        async def on_go(self):
            self.hop.put()
            await self.gate.wait()
            return "went"

        async def on_stall(self):
            self.stalling.set()
            await asyncio.Event().wait()

        def on_step(self):
            self.steps += 1
            return self.steps

        def on_hop(self):
            self.hops += 1

    return StalledRoad


class TestCancelledLockHolder:
    """Cancelling the coroutine that runs the processing loop cancels only that caller: a
    coroutine awaiting a queued event takes the loop over, and the machine stays usable.

    See: https://github.com/fgmacedo/python-statemachine/issues/690
    """

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_queued_callers_get_their_results(self):
        sm = stalled_road()()
        await sm.activate_initial_state()
        holder = asyncio.ensure_future(sm.send("go"))
        await asyncio.sleep(0)
        waiters = await queue_behind(sm, ("step", {}), ("step", {"delay": 50}), ("step", {}))

        await cancel_and_wait(holder)

        assert await asyncio.gather(*waiters) == [1, 3, 2]
        assert sm.configuration_values == {"start"}
        assert sm.hops == 0
        assert not sm._engine._processing.locked()

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_machine_takes_new_events_afterwards(self):
        sm = stalled_road()()
        await sm.activate_initial_state()
        holder = asyncio.ensure_future(sm.send("go"))
        await asyncio.sleep(0)

        await cancel_and_wait(holder)

        assert not sm._engine._processing.locked()
        assert sm._engine.internal_queue.is_empty()
        assert await sm.send("step") == 1
        assert sm.hops == 0

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_cancelled_while_waiting_for_a_delayed_event(self):
        sm = stalled_road()()
        await sm.activate_initial_state()
        holder = asyncio.ensure_future(sm.send("step", delay=100))
        await asyncio.sleep(0)
        (waiter,) = await queue_behind(sm, ("step", {"delay": 50}))

        await cancel_and_wait(holder)

        assert await waiter == 1
        assert sm.steps == 2
        assert sm._engine.external_queue.is_empty()
        assert not sm._engine._processing.locked()

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_caller_of_the_interrupted_event_gets_a_state_machine_error(self):
        sm = stalled_road()()
        await sm.activate_initial_state()
        holder = asyncio.ensure_future(sm.send("go"))
        await asyncio.sleep(0)
        stalled, stepper = await queue_behind(sm, ("stall", {}), ("step", {}))
        sm.gate.set()
        await sm.stalling.wait()

        await cancel_and_wait(holder)

        with pytest.raises(StateMachineError, match="was cancelled while"):
            await stalled
        assert await stepper == 1
        assert sm.configuration_values == {"road"}

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_cancelled_waiter_leaves_its_event_queued(self):
        sm = stalled_road()()
        await sm.activate_initial_state()
        holder = asyncio.ensure_future(sm.send("go"))
        await asyncio.sleep(0)
        gives_up, waiter = await queue_behind(sm, ("step", {}), ("step", {}))

        await cancel_and_wait(gives_up)
        sm.gate.set()

        assert await holder == "went"
        assert await waiter == 2
        assert sm.hops == 1

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio()
    async def test_cancelled_initial_activation_hands_the_loop_over(self):
        class SlowStart(StateMachine):
            booting = State(initial=True)
            ready = State(final=True)

            boot = booting.to(ready)

            async def on_enter_booting(self):
                await asyncio.Event().wait()

        sm = SlowStart()
        activation = asyncio.ensure_future(sm.activate_initial_state())
        await asyncio.sleep(0)
        (waiter,) = await queue_behind(sm, ("boot", {}))

        await cancel_and_wait(activation)

        assert await waiter is None
        assert sm.configuration_values == {"ready"}


class TestEventQueueRejectFutures:
    """Unit tests for EventQueue.reject_futures."""

    def test_reject_futures_skips_items_without_future(self):
        """Items with future=None are silently skipped."""
        sm = TrafficLight()

        queue = EventQueue()
        td = TriggerData(machine=sm, event=None)
        assert td.future is None
        queue.put(td)

        queue.reject_futures(RuntimeError("boom"))
        # No exception raised, item still in queue
        assert not queue.is_empty()
