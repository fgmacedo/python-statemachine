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

from statemachine import State
from statemachine import StateChart

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
        """When error_on_execution=False (not default for StateChart), the
        exception propagates to the caller of that event."""

        class FailingSC(StateChart):
            error_on_execution = False
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
    async def test_concurrent_sends_exception_with_error_on_execution_off(self):
        """When error_on_execution=False and one event raises, the exception
        is routed to that caller's future; the other caller is unaffected.

        With error_on_execution=False, the exception propagates and the
        processing loop clears the external queue, so the second event is
        never processed.
        """

        class ConcurrentFailMachine(StateChart):
            error_on_execution = False
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
            error_on_execution = False
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
