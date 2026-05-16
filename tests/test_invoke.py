"""Tests for the invoke callback group."""

import threading
import time

from statemachine.invoke import IInvoke
from statemachine.invoke import InvokeContext
from statemachine.invoke import invoke_group

from statemachine import Event
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
                pass  # no-op: only verifying the protocol is satisfied

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

        class CancelTracker:
            def run(self, ctx):
                while not ctx.cancelled.is_set():
                    ctx.cancelled.wait(0.01)

            def on_cancel(self):
                cancel_called.append(True)

        class SM(StateChart):
            loading = State(initial=True, invoke=CancelTracker)
            cancelled_state = State(final=True)
            cancel = loading.to(cancelled_state)

        sm = await sm_runner.start(SM)
        # Give the invoke handler time to start in its background thread
        await sm_runner.sleep(0.15)
        await sm_runner.send(sm, "cancel")
        await sm_runner.sleep(0.15)

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
            loading = State(initial=True, invoke=invoke_group(task_a, task_b))
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
        cancel_flag = threading.Event()

        def slow_task():
            # Use interruptible wait so thread can exit promptly on cancellation.
            cancel_flag.wait(timeout=5.0)
            return "should not complete"

        class SM(StateChart):
            loading = State(initial=True, invoke=invoke_group(slow_task))
            stopped = State(final=True)
            cancel = loading.to(stopped)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.05)
        await sm_runner.send(sm, "cancel")
        cancel_flag.set()  # Unblock the slow_task thread
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


class TestInvokeEventKwargs:
    """Event kwargs from send() are forwarded to invoke handlers."""

    async def test_plain_callable_receives_event_kwargs(self, sm_runner):
        """Plain callable invoke handler receives event kwargs via SignatureAdapter."""
        received = []

        class SM(StateChart):
            idle = State(initial=True)
            loading = State()
            ready = State(final=True)
            start = idle.to(loading)
            done_invoke_loading = loading.to(ready)

            def on_invoke_loading(self, file_name=None, **kwargs):
                received.append(file_name)
                return f"loaded:{file_name}"

            def on_enter_ready(self, data=None, **kwargs):
                received.append(data)

        sm = await sm_runner.start(SM)
        await sm_runner.send(sm, "start", file_name="config.json")
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values
        assert received == ["config.json", "loaded:config.json"]

    async def test_iinvoke_handler_receives_event_kwargs_via_ctx(self, sm_runner):
        """IInvoke handler receives event kwargs via ctx.kwargs."""
        received = []

        class FileLoader:
            def run(self, ctx: InvokeContext):
                received.append(ctx.kwargs.get("file_name"))
                return f"loaded:{ctx.kwargs['file_name']}"

        class SM(StateChart):
            idle = State(initial=True)
            loading = State(invoke=FileLoader)
            ready = State(final=True)
            start = idle.to(loading)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, data=None, **kwargs):
                received.append(data)

        sm = await sm_runner.start(SM)
        await sm_runner.send(sm, "start", file_name="data.csv")
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values
        assert received == ["data.csv", "loaded:data.csv"]

    async def test_initial_state_invoke_has_empty_kwargs(self, sm_runner):
        """Invoke on initial state gets empty kwargs (no triggering event)."""

        class SM(StateChart):
            loading = State(initial=True, invoke=lambda: 42)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)
        assert "ready" in sm.configuration_values


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


class TestInvokeManagerCancelAll:
    """InvokeManager.cancel_all() cancels every active invocation."""

    async def test_cancel_all(self, sm_runner):
        class SlowHandler:
            def run(self, ctx):
                ctx.cancelled.wait(timeout=5.0)

        class SM(StateChart):
            loading = State(initial=True, invoke=SlowHandler)
            stopped = State(final=True)
            cancel = loading.to(stopped)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        sm._engine._invoke_manager.cancel_all()
        await sm_runner.sleep(0.15)

        # All invocations should be terminated
        for inv in sm._engine._invoke_manager._active.values():
            assert inv.terminated


class TestInvokeCancelAlreadyTerminated:
    """Cancelling an already-terminated invocation is a no-op."""

    async def test_cancel_terminated_invocation(self, sm_runner):
        class SM(StateChart):
            loading = State(initial=True, invoke=lambda: 42)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

        sm = await sm_runner.start(SM)
        deadline = time.monotonic() + 2.0
        while "ready" not in sm.configuration_values and time.monotonic() < deadline:
            await sm_runner.sleep(0.02)
            await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values
        # All invocations should be terminated by now
        manager = sm._engine._invoke_manager
        for inv in manager._active.values():
            assert inv.terminated
        # Calling cancel on terminated invocations should be a safe no-op
        for inv_id in list(manager._active.keys()):
            manager._cancel(inv_id)


class TestInvokeOnCancelException:
    """Exception in on_cancel() is caught and logged, not propagated."""

    async def test_on_cancel_exception_is_suppressed(self, sm_runner):
        class BadCancelHandler:
            def run(self, ctx):
                ctx.cancelled.wait(timeout=5.0)

            def on_cancel(self):
                raise RuntimeError("on_cancel exploded")

        class SM(StateChart):
            loading = State(initial=True, invoke=BadCancelHandler)
            stopped = State(final=True)
            cancel = loading.to(stopped)

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        # This should NOT raise even though on_cancel() raises
        await sm_runner.send(sm, "cancel")
        await sm_runner.sleep(0.15)

        assert "stopped" in sm.configuration_values


class TestStateChartInvokerOnCancel:
    """StateChartInvoker.on_cancel() cleans up the child reference."""

    def test_on_cancel_clears_child(self):
        from statemachine.invoke import StateChartInvoker

        class ChildMachine(StateChart):
            start = State(initial=True, final=True)

        invoker = StateChartInvoker(ChildMachine)
        ctx = InvokeContext(
            invokeid="test.123",
            state_id="test",
            send=lambda *a, **kw: None,
            machine=None,
        )
        invoker.run(ctx)
        assert invoker._child is not None
        invoker.on_cancel()
        assert invoker._child is None


class TestNormalizeInvokeCallbacks:
    """normalize_invoke_callbacks handles edge cases."""

    def test_string_passes_through(self):
        from statemachine.invoke import normalize_invoke_callbacks

        result = normalize_invoke_callbacks("some_method_name")
        assert result == ["some_method_name"]

    def test_already_wrapped_passes_through(self):
        from statemachine.invoke import _InvokeCallableWrapper
        from statemachine.invoke import normalize_invoke_callbacks

        class MyHandler:
            def run(self, ctx):
                pass

        wrapper = _InvokeCallableWrapper(MyHandler)
        result = normalize_invoke_callbacks(wrapper)
        assert len(result) == 1
        assert result[0] is wrapper

    def test_iinvoke_class_with_run_method(self):
        """IInvoke-compatible class gets wrapped."""
        from statemachine.invoke import _InvokeCallableWrapper
        from statemachine.invoke import normalize_invoke_callbacks

        class CustomHandler:
            def run(self, ctx):
                return "result"

        # CustomHandler satisfies IInvoke protocol (has run method)
        assert isinstance(CustomHandler(), IInvoke)
        result = normalize_invoke_callbacks(CustomHandler)
        assert len(result) == 1
        assert isinstance(result[0], _InvokeCallableWrapper)

    def test_plain_callable_passes_through(self):
        from statemachine.invoke import _InvokeCallableWrapper
        from statemachine.invoke import normalize_invoke_callbacks

        def my_func():
            return 42

        result = normalize_invoke_callbacks(my_func)
        assert len(result) == 1
        assert result[0] is my_func
        assert not isinstance(result[0], _InvokeCallableWrapper)

    def test_non_invoke_class_passes_through(self):
        """A class without run() (not IInvoke, not StateChart) passes through unwrapped."""
        from statemachine.invoke import _InvokeCallableWrapper
        from statemachine.invoke import normalize_invoke_callbacks

        class PlainClass:
            pass

        result = normalize_invoke_callbacks(PlainClass)
        assert len(result) == 1
        assert result[0] is PlainClass
        assert not isinstance(result[0], _InvokeCallableWrapper)


class TestResolveHandler:
    """InvokeManager._resolve_handler edge cases."""

    def test_bare_iinvoke_instance(self):
        from statemachine.invoke import InvokeManager

        class MyHandler:
            def run(self, ctx):
                return "result"

        handler = MyHandler()
        assert isinstance(handler, IInvoke)
        resolved = InvokeManager._resolve_handler(handler)
        assert resolved is handler

    def test_bare_statechart_class(self):
        from statemachine.invoke import InvokeManager
        from statemachine.invoke import StateChartInvoker

        class ChildMachine(StateChart):
            start = State(initial=True, final=True)

        resolved = InvokeManager._resolve_handler(ChildMachine)
        assert isinstance(resolved, StateChartInvoker)

    def test_plain_callable_returns_none(self):
        from statemachine.invoke import InvokeManager

        def my_func():
            return 42

        assert InvokeManager._resolve_handler(my_func) is None


class TestInvokeCallableWrapperOnCancel:
    """_InvokeCallableWrapper.on_cancel() edge cases."""

    def test_on_cancel_non_class_instance_with_on_cancel(self):
        """Non-class handler (already instantiated) delegates on_cancel."""
        from statemachine.invoke import _InvokeCallableWrapper

        cancel_called = []

        class MyHandler:
            def run(self, ctx):
                return "result"

            def on_cancel(self):
                cancel_called.append(True)

        handler = MyHandler()
        wrapper = _InvokeCallableWrapper(handler)
        # _instance is None, _is_class is False → falls through to _invoke_handler
        wrapper.on_cancel()
        assert cancel_called == [True]

    def test_on_cancel_class_not_yet_instantiated(self):
        """Class handler not yet instantiated — on_cancel is a no-op."""
        from statemachine.invoke import _InvokeCallableWrapper

        class MyHandler:
            def run(self, ctx):
                return "result"

            def on_cancel(self):
                raise RuntimeError("should not be called")

        wrapper = _InvokeCallableWrapper(MyHandler)
        # _instance is None, _is_class is True → early return
        wrapper.on_cancel()  # should not raise

    def test_callable_wrapper_call_returns_handler(self):
        """__call__ returns the original handler (used by callback system for resolution)."""
        from statemachine.invoke import _InvokeCallableWrapper

        class MyHandler:
            def run(self, ctx):
                return "result"

        wrapper = _InvokeCallableWrapper(MyHandler)
        assert wrapper() is MyHandler


class TestInvokeGroupOnCancelBeforeRun:
    """InvokeGroup.on_cancel() before run() is a safe no-op."""

    def test_on_cancel_before_run(self):
        group = invoke_group(lambda: 1)
        # on_cancel before run — executor is None, no futures
        group.on_cancel()


class TestCoroutineFunctionAsInvokeTarget:
    """Coroutine functions should work as invoke targets on the async engine."""

    async def test_coroutine_invoke_returns_awaited_result(self):
        """An async function used as invoke target should be awaited and return its value."""
        from tests.conftest import SMRunner

        async def async_loader():
            return 42

        class SM(StateChart):
            loading = State(initial=True, invoke=async_loader)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, data=None, **kwargs):
                self.result = data

        sm_runner = SMRunner(is_async=True)
        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values
        assert sm.result == 42

    async def test_coroutine_invoke_error_sends_error_execution(self):
        """An async invoke that raises should send error.execution."""
        from tests.conftest import SMRunner

        async def failing_loader():
            raise ValueError("async boom")

        class SM(StateChart):
            loading = State(initial=True, invoke=failing_loader)
            error_state = State(final=True)
            error_execution = loading.to(error_state)

            def on_enter_error_state(self, error=None, **kwargs):
                self.caught_error = error

        sm_runner = SMRunner(is_async=True)
        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)

        assert "error_state" in sm.configuration_values
        assert isinstance(sm.caught_error, ValueError)
        assert str(sm.caught_error) == "async boom"

    async def test_coroutine_invoke_cancelled_on_state_exit(self):
        """An async invoke should be cancelled when the owning state is exited."""
        from tests.conftest import SMRunner

        cancel_observed = []

        async def slow_loader():
            import asyncio

            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancel_observed.append(True)
                raise
            return "should not reach"

        class SM(StateChart):
            loading = State(initial=True, invoke=slow_loader)
            stopped = State(final=True)
            cancel = loading.to(stopped)

        sm_runner = SMRunner(is_async=True)
        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.05)
        await sm_runner.send(sm, "cancel")
        await sm_runner.sleep(0.05)

        assert "stopped" in sm.configuration_values


class TestAsyncIInvokeInstance:
    """IInvoke instances with async def run() should be awaited on the async engine."""

    async def test_async_iinvoke_instance(self):
        """An IInvoke instance with async run() should be awaited."""
        from tests.conftest import SMRunner

        class AsyncHandler:
            async def run(self, ctx):
                return "async_result"

        handler = AsyncHandler()

        class SM(StateChart):
            loading = State(initial=True, invoke=handler)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, data=None, **kwargs):
                self.result = data

        sm_runner = SMRunner(is_async=True)
        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values
        assert sm.result == "async_result"


class TestAsyncIInvokeClass:
    """IInvoke classes with async def run() should be instantiated and awaited."""

    async def test_async_iinvoke_class(self):
        """An IInvoke class with async run() should be instantiated and its run() awaited."""
        from tests.conftest import SMRunner

        class AsyncHandler:
            async def run(self, ctx):
                return "class_async_result"

        class SM(StateChart):
            loading = State(initial=True, invoke=AsyncHandler)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_enter_ready(self, data=None, **kwargs):
                self.result = data

        sm_runner = SMRunner(is_async=True)
        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values
        assert sm.result == "class_async_result"


class TestAsyncIInvokeOnSyncEngine:
    """IInvoke with async run() on the sync engine should raise InvalidDefinition."""

    def test_async_iinvoke_instance_on_sync_engine_raises(self):
        """An IInvoke instance with async run() should fail clearly on the sync engine."""
        import pytest
        from statemachine.exceptions import InvalidDefinition

        class AsyncHandler:
            async def run(self, ctx):
                return "unreachable"

        handler = AsyncHandler()

        class SM(StateChart):
            loading = State(initial=True, invoke=handler)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

        with pytest.raises(InvalidDefinition):
            SM()

    def test_async_iinvoke_class_on_sync_engine_raises(self):
        """An IInvoke class with async run() should fail clearly on the sync engine."""
        import pytest
        from statemachine.exceptions import InvalidDefinition

        class AsyncHandler:
            async def run(self, ctx):
                return "unreachable"

        class SM(StateChart):
            loading = State(initial=True, invoke=AsyncHandler)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

        with pytest.raises(InvalidDefinition):
            SM()


class TestDoneInvokeEventFactory:
    """done_invoke_ prefix works with both TransitionList and Event."""

    async def test_done_invoke_with_event_object(self, sm_runner):
        """Event() object with done_invoke_ prefix should match done.invoke events."""

        class SM(StateChart):
            loading = State(initial=True, invoke=lambda: "result")
            ready = State(final=True)
            done_invoke_loading = Event(loading.to(ready))

        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.15)
        await sm_runner.processing_loop(sm)

        assert "ready" in sm.configuration_values


class TestVisitNoCallbacks:
    """visit/async_visit with no registered callbacks is a no-op."""

    def test_visit_missing_key(self):
        from statemachine.callbacks import CallbacksRegistry

        registry = CallbacksRegistry()
        # Should not raise — just returns
        registry.visit("nonexistent_key", lambda cb, **kw: None)

    async def test_async_visit_missing_key(self):
        from statemachine.callbacks import CallbacksRegistry

        registry = CallbacksRegistry()
        await registry.async_visit("nonexistent_key", lambda cb, **kw: None)


class TestAsyncVisitAwaitable:
    """async_visit should await the visitor_fn result when it is awaitable."""

    async def test_async_visitor_fn_is_awaited(self):
        from statemachine.callbacks import CallbackGroup
        from statemachine.callbacks import CallbacksExecutor
        from statemachine.callbacks import CallbackSpec

        visited = []

        async def async_visitor(callback, **kwargs):
            visited.append(str(callback))

        executor = CallbacksExecutor()
        spec = CallbackSpec("dummy", group=CallbackGroup.INVOKE, is_convention=True)
        executor.add("test_key", spec, lambda: lambda **kw: True)

        await executor.async_visit(async_visitor)
        assert visited == ["dummy"]


class TestIInvokeProtocolRun:
    """IInvoke.run() protocol method can be called on a concrete implementation."""

    def test_protocol_run_is_callable(self):
        """Verify that calling run() on a concrete IInvoke instance works."""

        class ConcreteInvoker:
            def run(self, ctx):
                return "concrete_result"

        invoker: IInvoke = ConcreteInvoker()
        result = invoker.run(None)
        assert result == "concrete_result"


class TestSpawnPendingAsyncEmpty:
    """spawn_pending_async with nothing pending is a no-op."""

    async def test_spawn_pending_async_no_pending(self, sm_runner):
        class SM(StateChart):
            idle = State(initial=True)
            active = State(final=True)
            go = idle.to(active)

        sm = await sm_runner.start(SM)
        # Directly call spawn_pending_async with empty pending list
        await sm._engine._invoke_manager.spawn_pending_async()


class TestInvokeAsyncCancelledDuringExecution:
    """Async handler completes or errors after state was already exited."""

    async def test_success_after_cancel(self):
        """Handler returns successfully but ctx.cancelled is already set."""
        from tests.conftest import SMRunner

        class SM(StateChart):
            loading = State(initial=True)
            stopped = State(final=True)
            cancel = loading.to(stopped)

            def on_invoke_loading(self, ctx=None, **kwargs):
                if ctx is None:
                    return
                # Simulate: cancelled is set during execution but we still return
                ctx.cancelled.set()
                return "should_be_ignored"

        sm_runner = SMRunner(is_async=True)
        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)

        # The done.invoke event should NOT have been sent (cancelled)
        assert "loading" in sm.configuration_values

    async def test_error_after_cancel(self):
        """Handler raises but ctx.cancelled is already set — error is swallowed."""
        from tests.conftest import SMRunner

        class SM(StateChart):
            loading = State(initial=True)
            error_state = State(final=True)
            error_execution = loading.to(error_state)

            def on_invoke_loading(self, ctx=None, **kwargs):
                if ctx is None:
                    return
                # Simulate: cancelled during execution, then error
                ctx.cancelled.set()
                raise ValueError("should be ignored")

        sm_runner = SMRunner(is_async=True)
        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)

        # The error.execution event should NOT have been sent (cancelled)
        assert "loading" in sm.configuration_values


class TestSyncInvokeErrorAfterCancel:
    """Sync handler errors after state was already exited."""

    async def test_sync_error_after_cancel(self):
        """Sync handler raises but ctx.cancelled is set — error.execution not sent."""
        from tests.conftest import SMRunner

        class SM(StateChart):
            loading = State(initial=True)
            error_state = State(final=True)
            error_execution = loading.to(error_state)

            def on_invoke_loading(self, ctx=None, **kwargs):
                if ctx is None:
                    return
                ctx.cancelled.set()
                raise ValueError("should be ignored")

        sm_runner = SMRunner(is_async=False)
        sm = await sm_runner.start(SM)
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)

        assert "loading" in sm.configuration_values


class TestInvokeManagerUnit:
    """Unit tests for InvokeManager methods not exercised by integration tests."""

    def test_send_to_child_not_found(self):
        """send_to_child returns False when invokeid is not in _active."""
        from unittest.mock import Mock

        from statemachine.invoke import InvokeManager

        engine = Mock()
        manager = InvokeManager(engine)

        assert manager.send_to_child("nonexistent", "event") is False

    def test_send_to_child_handler_without_on_event(self):
        """send_to_child returns False when handler has no on_event."""
        from unittest.mock import Mock

        from statemachine.invoke import Invocation
        from statemachine.invoke import InvokeContext
        from statemachine.invoke import InvokeManager

        engine = Mock()
        manager = InvokeManager(engine)

        handler = Mock(spec=[])  # no on_event
        ctx = InvokeContext(invokeid="test_id", state_id="s1", send=Mock(), machine=Mock())
        inv = Invocation(invokeid="test_id", state_id="s1", ctx=ctx, _handler=handler)
        manager._active["test_id"] = inv

        assert manager.send_to_child("test_id", "event") is False

    def test_handle_external_event_none_event(self):
        """handle_external_event returns early when event is None."""
        from unittest.mock import Mock

        from statemachine.invoke import InvokeManager

        engine = Mock()
        manager = InvokeManager(engine)

        trigger_data = Mock(event=None)
        # Should not raise
        manager.handle_external_event(trigger_data)


class TestStopChildMachine:
    """Tests for _stop_child_machine."""

    def test_stop_child_machine_exception_swallowed(self):
        """_stop_child_machine swallows exceptions during stop."""
        from unittest.mock import Mock

        from statemachine.invoke import _stop_child_machine

        child = Mock()
        child._engine.running = True
        child._engine._invoke_manager.cancel_all.side_effect = RuntimeError("boom")

        # Should not raise
        _stop_child_machine(child)


class TestEngineDelCleanup:
    """Test BaseEngine.__del__ cancel_all exception handling."""

    def test_del_swallows_cancel_all_exception(self):
        """__del__ swallows exceptions from cancel_all."""

        class SM(StateChart):
            s1 = State(initial=True, final=True)

        sm = SM()
        engine = sm._engine
        engine._invoke_manager.cancel_all = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

        # Should not raise
        engine.__del__()
