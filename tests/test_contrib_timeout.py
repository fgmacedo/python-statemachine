"""Tests for the timeout contrib module."""

import threading

import pytest
from statemachine.contrib.timeout import _Timeout
from statemachine.contrib.timeout import timeout

from statemachine import State
from statemachine import StateChart


class TestTimeoutValidation:
    def test_positive_duration(self):
        t = timeout(5)
        assert isinstance(t, _Timeout)
        assert t.duration == 5

    def test_zero_duration_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            timeout(0)

    def test_negative_duration_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            timeout(-1)

    def test_repr_without_on(self):
        assert repr(timeout(5)) == "timeout(5)"

    def test_repr_with_on(self):
        assert repr(timeout(3.5, on="expired")) == "timeout(3.5, on='expired')"


class TestTimeoutBasic:
    """Timeout fires done.invoke.<state> when no custom event is specified."""

    async def test_timeout_fires_done_invoke(self, sm_runner):
        class SM(StateChart):
            waiting = State(initial=True, invoke=timeout(0.05))
            done = State(final=True)
            done_invoke_waiting = waiting.to(done)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "done" in sm.configuration_values

    async def test_timeout_cancelled_on_early_exit(self, sm_runner):
        """If the machine transitions out before the timeout, nothing fires."""

        class SM(StateChart):
            waiting = State(initial=True, invoke=timeout(10))
            other = State(final=True)
            go = waiting.to(other)
            # No done_invoke_waiting — would fail if timeout fired unexpectedly
            done_invoke_waiting = waiting.to(waiting)

        sm = await sm_runner.start(SM)
        await sm_runner.send(sm, "go")

        assert "other" in sm.configuration_values


class TestTimeoutCustomEvent:
    """Timeout fires a custom event via the `on` parameter."""

    async def test_custom_event_fires(self, sm_runner):
        class SM(StateChart):
            waiting = State(initial=True, invoke=timeout(0.05, on="expired"))
            timed_out = State(final=True)
            expired = waiting.to(timed_out)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "timed_out" in sm.configuration_values

    async def test_custom_event_cancelled_on_early_exit(self, sm_runner):
        class SM(StateChart):
            waiting = State(initial=True, invoke=timeout(10, on="expired"))
            other = State(final=True)
            go = waiting.to(other)
            expired = waiting.to(waiting)

        sm = await sm_runner.start(SM)
        await sm_runner.send(sm, "go")

        assert "other" in sm.configuration_values


class TestTimeoutComposition:
    """Timeout combined with other invoke handlers — first to complete wins."""

    async def test_invoke_completes_before_timeout(self, sm_runner):
        """A fast invoke handler transitions out, cancelling the timeout."""

        def fast_handler():
            return "fast_result"

        class SM(StateChart):
            loading = State(initial=True, invoke=[fast_handler, timeout(10, on="too_slow")])
            ready = State(final=True)
            stuck = State(final=True)
            done_invoke_loading = loading.to(ready)
            too_slow = loading.to(stuck)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values

    async def test_timeout_fires_before_slow_invoke(self, sm_runner):
        """Timeout fires while a slow invoke handler is still running."""
        handler_cancelled = threading.Event()

        class SlowHandler:
            def run(self, ctx):
                # Wait until cancelled (state exit) — simulates long-running work
                ctx.cancelled.wait()
                handler_cancelled.set()

        class SM(StateChart):
            loading = State(initial=True, invoke=[SlowHandler(), timeout(0.05, on="too_slow")])
            ready = State(final=True)
            stuck = State(final=True)
            done_invoke_loading = loading.to(ready)
            too_slow = loading.to(stuck)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "stuck" in sm.configuration_values
        # The slow handler should have been cancelled when the state exited
        handler_cancelled.wait(timeout=2)
        assert handler_cancelled.is_set()
