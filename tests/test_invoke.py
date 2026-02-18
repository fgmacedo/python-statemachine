"""Tests for the invoke callback group."""

import threading
import time

from statemachine.invoke import IInvoke
from statemachine.invoke import InvokeContext
from statemachine.invoke import invoke_group

from statemachine import State
from statemachine import StateChart


class TestInvokeSimpleCallable:
    """Simple callable invoke — function runs in background, done.invoke fires."""

    async def test_simple_callable_invoke(self, sm_runner):
        results = []

        class SM(StateChart):
            loading = State(initial=True, invoke=lambda: 42)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, data=None, **kwargs):
                results.append(data)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values
        assert results == [42]

    async def test_invoke_return_value_in_done_event(self, sm_runner):
        results = []

        class SM(StateChart):
            loading = State(initial=True, invoke=lambda: {"key": "value"})
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, data=None, **kwargs):
                results.append(data)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values
        assert results == [{"key": "value"}]


class TestInvokeNamingConvention:
    """Naming convention — on_invoke_<state>() method is discovered and invoked."""

    async def test_naming_convention(self, sm_runner):
        invoked = []

        class SM(StateChart):
            loading = State(initial=True)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_invoke_loading(self, **kwargs):
                invoked.append(True)
                return "done"

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert invoked == [True]
        assert "ready" in sm.configuration_values


class TestInvokeDecorator:
    """Decorator — @state.invoke handler."""

    async def test_decorator_invoke(self, sm_runner):
        invoked = []

        class SM(StateChart):
            loading = State(initial=True)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            @loading.invoke
            def do_work(self, **kwargs):
                invoked.append(True)
                return "result"

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert invoked == [True]
        assert "ready" in sm.configuration_values


class TestInvokeIInvokeProtocol:
    """IInvoke protocol — class with run(ctx) method."""

    async def test_iinvoke_class(self, sm_runner):
        """Pass an IInvoke class — engine instantiates per SM instance."""
        results = []

        class MyInvoker:
            def run(self, ctx: InvokeContext):
                results.append(ctx.state_id)
                return "invoker_result"

            def on_cancel(self):
                pass

        assert isinstance(MyInvoker(), IInvoke)

        class SM(StateChart):
            loading = State(initial=True, invoke=MyInvoker)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, data=None, **kwargs):
                results.append(data)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "loading" in results
        assert "invoker_result" in results
        assert "ready" in sm.configuration_values

    async def test_each_sm_instance_gets_own_handler(self, sm_runner):
        """Each StateChart instance must get a fresh IInvoke instance."""
        handler_ids = []

        class TrackingInvoker:
            def run(self, ctx: InvokeContext):
                handler_ids.append(id(self))
                return None

        class SM(StateChart):
            loading = State(initial=True, invoke=TrackingInvoker)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

        sm1 = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm1)

        sm2 = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm2)

        assert len(handler_ids) == 2
        assert handler_ids[0] != handler_ids[1], "Each SM must get its own handler instance"


class TestInvokeCancelOnExit:
    """Cancel on exit — ctx.cancelled is set when state is exited."""

    async def test_cancel_on_exit_sync(self):
        """Test cancel in sync mode only — uses threading.Event.wait()."""
        from tests.conftest import SMRunner

        sm_runner = SMRunner(is_async=False)
        cancel_observed = []

        class SM(StateChart):
            loading = State(initial=True)
            cancelled_state = State(final=True)
            cancel = loading.to(cancelled_state)

            def on_invoke_loading(self, ctx=None, **kwargs):
                if ctx is None:
                    return
                ctx.cancelled.wait(timeout=5.0)
                cancel_observed.append(ctx.cancelled.is_set())

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.05)
        await sm_runner.send(sm, "cancel")
        await sm_runner.sleep(0.1)

        assert cancel_observed == [True]
        assert "cancelled_state" in sm.configuration_values

    async def test_cancel_on_exit_with_on_cancel(self, sm_runner):
        """Test that on_cancel() is called when state is exited."""
        cancel_called = []
        started = threading.Event()

        class CancelTracker:
            def run(self, ctx):
                started.set()
                # Poll instead of blocking to work with both sync and async engines
                while not ctx.cancelled.is_set():
                    ctx.cancelled.wait(0.01)

            def on_cancel(self):
                cancel_called.append(True)

        class SM(StateChart):
            loading = State(initial=True, invoke=CancelTracker)
            cancelled_state = State(final=True)
            cancel = loading.to(cancelled_state)

        sm = await sm_runner.start(SM)
        # Wait for invoke handler to start (runs in thread for sync, task for async)
        await sm_runner.sleep(0.05)
        await sm_runner.send(sm, "cancel")
        await sm_runner.sleep(0.05)

        assert cancel_called == [True]
        assert "cancelled_state" in sm.configuration_values


class TestInvokeErrorHandling:
    """Error in invoker → error.execution event."""

    async def test_error_in_invoke(self, sm_runner):
        errors = []

        class SM(StateChart):
            loading = State(initial=True, invoke=lambda: 1 / 0)
            error_state = State(final=True)
            error_execution = loading.to(error_state)

            def on_enter_error_state(self, **kwargs):
                errors.append(True)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert errors == [True]
        assert "error_state" in sm.configuration_values


class TestInvokeMultiple:
    """Multiple invokes per state — all run concurrently."""

    async def test_multiple_invokes(self, sm_runner):
        results = []
        lock = threading.Lock()

        def task_a():
            with lock:
                results.append("a")
            return "a"

        def task_b():
            with lock:
                results.append("b")
            return "b"

        class SM(StateChart):
            loading = State(initial=True, invoke=[task_a, task_b])
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)

        assert sorted(results) == ["a", "b"]


class TestInvokeStateChartChild:
    """StateChart as invoker — child machine runs, completion fires done event."""

    async def test_statechart_invoker(self, sm_runner):
        class ChildMachine(StateChart):
            start = State(initial=True)
            end = State(final=True)
            go = start.to(end)

            def on_enter_start(self, **kwargs):
                self.send("go")

        class SM(StateChart):
            loading = State(initial=True, invoke=ChildMachine)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values


class TestDoneInvokeTransition:
    """done_invoke_<state> transition — naming convention works."""

    async def test_done_invoke_transition(self, sm_runner):
        class SM(StateChart):
            loading = State(initial=True, invoke=lambda: "hello")
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values


class TestDoneInvokeEventFormat:
    """done.invoke event name must be done.invoke.<state_id>.<platform_id> (no duplication)."""

    async def test_done_invoke_event_has_no_duplicate_state_id(self, sm_runner):
        received_events = []

        class SM(StateChart):
            loading = State(initial=True, invoke=lambda: "ok")
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, event=None, **kwargs):
                if event is not None:
                    received_events.append(str(event))

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert len(received_events) == 1
        event_name = received_events[0]
        # Must be "done.invoke.loading.<hex>" — NOT "done.invoke.loading.loading.<hex>"
        assert event_name.startswith("done.invoke.loading.")
        parts = event_name.split(".")
        # ["done", "invoke", "loading", "<hex>"] — exactly 4 parts
        assert len(parts) == 4, f"Expected 4 parts, got {parts}"


class TestInvokeGroup:
    """invoke_group() — runs multiple callables concurrently, returns list of results."""

    async def test_group_returns_ordered_results(self, sm_runner):
        """Results are returned in the same order as the input callables."""
        results = []

        def slow():
            time.sleep(0.05)
            return "slow"

        def fast():
            return "fast"

        class SM(StateChart):
            loading = State(initial=True, invoke=invoke_group(slow, fast))
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, data=None, **kwargs):
                results.append(data)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values
        assert results == [["slow", "fast"]]

    async def test_group_with_file_io(self, sm_runner, tmp_path):
        """Real I/O: read two files concurrently and get both results."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("hello")
        file_b.write_text("world")

        results = []

        class SM(StateChart):
            loading = State(
                initial=True,
                invoke=invoke_group(
                    lambda: file_a.read_text(),
                    lambda: file_b.read_text(),
                ),
            )
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, data=None, **kwargs):
                results.append(data)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values
        assert results == [["hello", "world"]]

    async def test_group_error_cancels_remaining(self, sm_runner):
        """If one callable raises, error.execution is sent."""
        errors = []

        def ok():
            time.sleep(0.1)
            return "ok"

        def fail():
            raise ValueError("boom")

        class SM(StateChart):
            loading = State(initial=True, invoke=invoke_group(ok, fail))
            error_state = State(final=True)
            error_execution = loading.to(error_state)

            def on_enter_error_state(self, **kwargs):
                errors.append(True)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.3)
        await sm_runner.processing_loop(sm)

        assert "error_state" in sm.configuration_values
        assert errors == [True]

    async def test_group_cancel_on_exit(self, sm_runner):
        """Cancellation propagates: exiting state stops the group."""

        def slow_task():
            time.sleep(5.0)
            return "should not complete"

        class SM(StateChart):
            loading = State(initial=True, invoke=invoke_group(slow_task))
            stopped = State(final=True)
            cancel = loading.to(stopped)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.05)
        await sm_runner.send(sm, "cancel")
        await sm_runner.sleep(0.1)

        assert "stopped" in sm.configuration_values

    async def test_group_single_callable(self, sm_runner):
        """Edge case: group with a single callable still returns a list."""
        results = []

        class SM(StateChart):
            loading = State(initial=True, invoke=invoke_group(lambda: 42))
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, data=None, **kwargs):
                results.append(data)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values
        assert results == [[42]]

    async def test_each_sm_instance_gets_own_group(self, sm_runner):
        """Each SM instance must get its own InvokeGroup — no shared state."""
        all_results = []

        counter = {"value": 0}
        lock = threading.Lock()

        def counting_task():
            with lock:
                counter["value"] += 1
                return counter["value"]

        class SM(StateChart):
            loading = State(initial=True, invoke=invoke_group(counting_task))
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, data=None, **kwargs):
                all_results.append(data)

        sm1 = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm1)

        sm2 = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm2)

        assert len(all_results) == 2
        assert all_results[0] == [1]
        assert all_results[1] == [2]


class TestInvokeNotTriggeredOnNonInvokeState:
    """States without invoke handlers should not be affected."""

    async def test_no_invoke_on_plain_state(self, sm_runner):
        class SM(StateChart):
            idle = State(initial=True)
            active = State()
            done = State(final=True)

            go = idle.to(active)
            finish = active.to(done)

        sm = await sm_runner.start(SM)
        await sm_runner.send(sm, "go")
        assert "active" in sm.configuration_values
        await sm_runner.send(sm, "finish")
        assert "done" in sm.configuration_values
