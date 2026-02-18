"""Unit tests for the Python invoke API (State(invoke=...) and done_invoke_ convention)."""

import asyncio
import time

import pytest
from statemachine.invoke import InvokeConfig
from statemachine.invoke import Invoker
from statemachine.invoke import StateChartInvoker

from statemachine import State
from statemachine import StateChart


class ChildMachine(StateChart):
    """A simple child that immediately reaches its final state via eventless transition."""

    s1 = State(initial=True)
    done = State(final=True)

    # Eventless transition — fires automatically on entry
    s1.to(done)


class SlowChild(StateChart):
    """A child that waits for an external event before finishing."""

    waiting = State(initial=True)
    done = State(final=True)

    go = waiting.to(done)


# --- Helpers ---


def _wait_for_state(sm, state_id, timeout=3.0, poll=0.02):
    """Poll until the state machine reaches the given state or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if state_id in sm.configuration_values:
            return True
        time.sleep(poll)
    return False


async def _async_wait_for_state(sm, state_id, timeout=3.0, poll=0.02):
    """Async poll until the state machine reaches the given state or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if state_id in sm.configuration_values:
            return True
        await asyncio.sleep(poll)
    return False


async def _wait_for(sm_runner, sm, state_id, timeout=3.0):
    """Wait for state using sync or async polling based on runner."""
    if sm_runner.is_async:
        return await _async_wait_for_state(sm, state_id, timeout=timeout)
    return _wait_for_state(sm, state_id, timeout=timeout)


async def _sleep(sm_runner, seconds=0.1):
    if sm_runner.is_async:
        await asyncio.sleep(seconds)
    else:
        time.sleep(seconds)


# --- Tests ---


class TestStateInvokeNormalization:
    """Test that State(invoke=...) normalizes various input types."""

    def test_invoke_none(self):
        s = State(invoke=None)
        assert s.invocations == []

    def test_invoke_statechart_becomes_invoke_config_with_handler(self):
        s = State(invoke=ChildMachine)
        assert len(s.invocations) == 1
        assert isinstance(s.invocations[0], InvokeConfig)
        assert isinstance(s.invocations[0].handler, StateChartInvoker)
        assert s.invocations[0].handler._child_class is ChildMachine

    def test_invoke_config_passthrough(self):
        config = InvokeConfig(handler=StateChartInvoker(ChildMachine))
        s = State(invoke=config)
        assert len(s.invocations) == 1
        assert s.invocations[0] is config

    def test_invoke_callable_goes_to_invoke_specs(self):
        def my_handler(ctx):
            return {"result": 42}

        s = State(invoke=my_handler)
        # Callables (non-class) are now routed to invoke_specs (callback-based invoke)
        assert len(s.invocations) == 0
        assert len(list(s.invoke_specs)) > 0

    def test_invoke_string_goes_to_invoke_specs(self):
        s = State(invoke="my_method")
        assert len(s.invocations) == 0
        assert any(spec.func == "my_method" for spec in s.invoke_specs)

    def test_invoke_invoker_class_becomes_invoke_config(self):
        class MyInvoker:
            def run(self, ctx):
                return None

        s = State(invoke=MyInvoker)
        assert len(s.invocations) == 1
        assert isinstance(s.invocations[0], InvokeConfig)
        # MyInvoker is a class (type), so it goes to invocations
        assert s.invocations[0].handler is MyInvoker

    def test_invoke_list_of_classes(self):
        s = State(invoke=[ChildMachine, SlowChild])
        assert len(s.invocations) == 2
        assert isinstance(s.invocations[0].handler, StateChartInvoker)
        assert isinstance(s.invocations[1].handler, StateChartInvoker)
        assert s.invocations[0].handler._child_class is ChildMachine
        assert s.invocations[1].handler._child_class is SlowChild

    def test_invoke_list_mixed(self):
        def my_handler(ctx):
            return None

        s = State(invoke=[ChildMachine, my_handler])
        # ChildMachine → invocations, my_handler (callable) → invoke_specs
        assert len(s.invocations) == 1
        assert isinstance(s.invocations[0].handler, StateChartInvoker)
        assert len(list(s.invoke_specs)) > 0


class TestInvokerProtocol:
    """Test that the Invoker protocol works with runtime_checkable."""

    def test_class_with_run_satisfies_protocol(self):
        class MyHandler:
            def run(self, ctx):
                return None

        assert isinstance(MyHandler(), Invoker)

    def test_plain_function_does_not_satisfy_protocol(self):
        def handler(ctx):
            return None

        # Functions don't have a run() method
        assert not isinstance(handler, Invoker)


class TestDoneInvokeNamingConvention:
    """Test that done_invoke_<state> registers the done.invoke.<state> event."""

    def test_done_invoke_event_registered(self):
        class Parent(StateChart):
            active = State(initial=True, invoke=ChildMachine)
            completed = State(final=True)

            done_invoke_active = active.to(completed)

        event_ids = {e.id for e in Parent.events}
        assert any("done.invoke.active" in eid for eid in event_ids)

    @pytest.mark.asyncio()
    async def test_done_invoke_transition_fires(self, sm_runner):
        """When the child terminates, done.invoke.<state> fires on the parent."""

        class Parent(StateChart):
            active = State(initial=True, invoke=ChildMachine)
            completed = State(final=True)

            done_invoke_active = active.to(completed)

        sm = await sm_runner.start(Parent)
        reached = await _wait_for(sm_runner, sm, "completed")
        assert reached, f"Parent did not reach 'completed'. Config: {sm.configuration_values}"


class TestInvokeSpawnAndCancel:
    """Test basic invoke lifecycle: spawn on entry, cancel on exit."""

    @pytest.mark.asyncio()
    async def test_child_spawned_on_state_entry(self, sm_runner):
        """When entering a state with invoke, a child session should be spawned."""

        class Parent(StateChart):
            idle = State(initial=True)
            active = State(invoke=SlowChild)
            done = State(final=True)

            start = idle.to(active)
            done_invoke_active = active.to(done)

        sm = await sm_runner.start(Parent)
        await sm_runner.send(sm, "start")
        await _sleep(sm_runner)

        active = sm._engine._invoke._active
        assert len(active) > 0, "No active invocations found after entering invoke state"

    @pytest.mark.asyncio()
    async def test_child_cancelled_on_state_exit(self, sm_runner):
        """When the parent exits the invoking state, the child is cancelled."""

        class Parent(StateChart):
            idle = State(initial=True)
            active = State(invoke=SlowChild)
            other = State()
            done = State(final=True)

            start = idle.to(active)
            abort = active.to(other)
            finish = other.to(done)

        sm = await sm_runner.start(Parent)
        await sm_runner.send(sm, "start")
        await _sleep(sm_runner)

        active_before = list(sm._engine._invoke._active.values())
        assert len(active_before) > 0

        await sm_runner.send(sm, "abort")
        # Check that the context was cancelled
        inv = active_before[0]
        assert inv.ctx is not None, "Child ctx should not be None"
        assert inv.ctx.cancelled, "Child ctx was not cancelled after exiting invoke state"


class TestCallableHandler:
    """Test using a plain function as an invoke handler."""

    @pytest.mark.asyncio()
    async def test_function_handler_return_data(self, sm_runner):
        """A function handler's return value is sent as done.invoke data."""
        received_data = {}

        class FetchHandler:
            def run(self, ctx):
                return {"answer": 42}

        class Parent(StateChart):
            active = State(initial=True, invoke=FetchHandler)
            completed = State(final=True)

            done_invoke_active = active.to(completed)

            def on_done_invoke_active(self, answer=None, **kwargs):
                received_data["answer"] = answer

        sm = await sm_runner.start(Parent)
        reached = await _wait_for(sm_runner, sm, "completed")
        assert reached, f"Parent did not reach 'completed'. Config: {sm.configuration_values}"
        assert received_data.get("answer") == 42


class TestInvokerClassHandler:
    """Test using a class with run() method as an invoke handler."""

    @pytest.mark.asyncio()
    async def test_class_handler_with_on_cancel(self, sm_runner):
        """A class handler's on_cancel() is called when the parent exits."""
        cancel_called = []

        class MyHandler:
            def run(self, ctx):
                while not ctx.cancelled:
                    time.sleep(0.01)
                return None

            def on_cancel(self):
                cancel_called.append(True)

        class Parent(StateChart):
            idle = State(initial=True)
            active = State(invoke=MyHandler)
            other = State()
            done = State(final=True)

            start = idle.to(active)
            abort = active.to(other)
            finish = other.to(done)

        sm = await sm_runner.start(Parent)
        await sm_runner.send(sm, "start")
        await _sleep(sm_runner)
        await sm_runner.send(sm, "abort")
        await _sleep(sm_runner, 0.2)

        assert len(cancel_called) > 0, "on_cancel() was not called"

    @pytest.mark.asyncio()
    async def test_class_handler_with_on_event(self, sm_runner):
        """A class handler's on_event() receives autoforwarded events."""
        forwarded_events = []

        class MyHandler:
            autoforward = True

            def run(self, ctx):
                while not ctx.cancelled:
                    time.sleep(0.01)
                return None

            def on_event(self, event, **data):
                forwarded_events.append(event)

        class Parent(StateChart):
            idle = State(initial=True)
            active = State(invoke=InvokeConfig(handler=MyHandler))
            other = State()
            done = State(final=True)

            start = idle.to(active)
            abort = active.to(other)
            finish = other.to(done)

        sm = await sm_runner.start(Parent)
        await sm_runner.send(sm, "start")
        await _sleep(sm_runner)
        # Send abort — should be autoforwarded to handler before transition
        await sm_runner.send(sm, "abort")
        await _sleep(sm_runner, 0.2)

        assert "abort" in forwarded_events, (
            f"on_event() was not called with 'abort'. Got: {forwarded_events}"
        )


class TestMultipleInvocations:
    """Test invoking multiple children from the same state."""

    def test_multiple_invoke_configs(self):
        class Parent(StateChart):
            active = State(initial=True, invoke=[ChildMachine, ChildMachine])
            done = State(final=True)

            done_invoke_active = active.to(done)

        assert len(Parent.states_map["active"].invocations) == 2


# --- Callback-based invoke tests ---


class TestCallbackBasedInvoke:
    """Test the callback-based invoke system (on_invoke_<state>, string, callable)."""

    @pytest.mark.asyncio()
    async def test_naming_convention_on_invoke_state(self, sm_runner):
        """Defining on_invoke_<state> triggers callback-based invoke and done.invoke."""
        invoked = []

        class Parent(StateChart):
            active = State(initial=True)
            completed = State(final=True)

            done_invoke_active = active.to(completed)

            def on_invoke_active(self, **kwargs):
                invoked.append(True)
                return {"answer": 42}

        sm = await sm_runner.start(Parent)
        reached = await _wait_for(sm_runner, sm, "completed")
        assert reached, f"Parent did not reach 'completed'. Config: {sm.configuration_values}"
        assert len(invoked) > 0, "on_invoke_active was not called"

    @pytest.mark.asyncio()
    async def test_naming_convention_return_data(self, sm_runner):
        """Return data from on_invoke_<state> is forwarded via done.invoke event."""
        received_data = {}

        class Parent(StateChart):
            active = State(initial=True)
            completed = State(final=True)

            done_invoke_active = active.to(completed)

            def on_invoke_active(self, **kwargs):
                return {"answer": 42}

            def on_done_invoke_active(self, answer=None, **kwargs):
                received_data["answer"] = answer

        sm = await sm_runner.start(Parent)
        reached = await _wait_for(sm_runner, sm, "completed")
        assert reached, f"Parent did not reach 'completed'. Config: {sm.configuration_values}"
        assert received_data.get("answer") == 42

    @pytest.mark.asyncio()
    async def test_explicit_invoke_string(self, sm_runner):
        """State(invoke='method_name') invokes the named method."""
        invoked = []

        class Parent(StateChart):
            active = State(initial=True, invoke="do_work")
            completed = State(final=True)

            done_invoke_active = active.to(completed)

            def do_work(self, **kwargs):
                invoked.append(True)
                return {"result": "ok"}

        sm = await sm_runner.start(Parent)
        reached = await _wait_for(sm_runner, sm, "completed")
        assert reached, f"Parent did not reach 'completed'. Config: {sm.configuration_values}"
        assert len(invoked) > 0, "do_work was not called"

    @pytest.mark.asyncio()
    async def test_invoke_callable(self, sm_runner):
        """State(invoke=callable) invokes the callable via callback system."""
        invoked = []

        def my_task(**kwargs):
            invoked.append(True)
            return {"done": True}

        class Parent(StateChart):
            active = State(initial=True, invoke=my_task)
            completed = State(final=True)

            done_invoke_active = active.to(completed)

        sm = await sm_runner.start(Parent)
        reached = await _wait_for(sm_runner, sm, "completed")
        assert reached, f"Parent did not reach 'completed'. Config: {sm.configuration_values}"
        assert len(invoked) > 0, "my_task was not called"

    @pytest.mark.asyncio()
    async def test_cancellation_via_threading_event(self, sm_runner):
        """Callback-based invoke receives a threading.Event for cooperative cancellation."""
        cancel_observed = []

        class Parent(StateChart):
            idle = State(initial=True)
            active = State()
            other = State()
            done = State(final=True)

            start = idle.to(active)
            abort = active.to(other)
            finish = other.to(done)

            def on_invoke_active(self, cancelled=None, **kwargs):
                # Wait for cancellation
                if cancelled is not None:
                    cancelled.wait(timeout=5.0)
                    cancel_observed.append(cancelled.is_set())

        sm = await sm_runner.start(Parent)
        await sm_runner.send(sm, "start")
        await _sleep(sm_runner, 0.1)
        await sm_runner.send(sm, "abort")
        await _sleep(sm_runner, 0.3)

        assert len(cancel_observed) > 0, "on_invoke_active was not called or didn't complete"
        assert cancel_observed[0] is True, "cancelled event was not set"

    @pytest.mark.asyncio()
    async def test_without_cancelled_param(self, sm_runner):
        """Callback-based invoke works fine without accepting 'cancelled' param."""
        invoked = []

        class Parent(StateChart):
            active = State(initial=True)
            completed = State(final=True)

            done_invoke_active = active.to(completed)

            def on_invoke_active(self, **kwargs):
                invoked.append(True)
                return {"status": "done"}

        sm = await sm_runner.start(Parent)
        reached = await _wait_for(sm_runner, sm, "completed")
        assert reached, f"Parent did not reach 'completed'. Config: {sm.configuration_values}"
        assert len(invoked) > 0

    @pytest.mark.asyncio()
    async def test_coexistence_with_child_machine(self, sm_runner):
        """Callback invoke and child SM invoke can coexist on the same state."""
        callback_invoked = []

        class Parent(StateChart):
            active = State(initial=True, invoke=ChildMachine)
            completed = State(final=True)

            done_invoke_active = active.to(completed)

            def on_invoke_active(self, **kwargs):
                callback_invoked.append(True)
                return None

        sm = await sm_runner.start(Parent)
        reached = await _wait_for(sm_runner, sm, "completed")
        assert reached, f"Parent did not reach 'completed'. Config: {sm.configuration_values}"
        assert len(callback_invoked) > 0, "on_invoke_active callback was not called"

    @pytest.mark.asyncio()
    async def test_error_triggers_error_execution(self, sm_runner):
        """Error in callback-based invoke triggers error.execution."""
        error_received = []

        class Parent(StateChart):
            active = State(initial=True)
            error_state = State()
            completed = State(final=True)

            error_execution = active.to(error_state)
            done = error_state.to(completed)

            def on_invoke_active(self, **kwargs):
                raise ValueError("invoke failed")

            def on_enter_error_state(self, **kwargs):
                error_received.append(True)

        await sm_runner.start(Parent)
        await _sleep(sm_runner, 0.5)
        # Should have transitioned to error_state via error.execution
        assert len(error_received) > 0, "error.execution was not triggered"

    @pytest.mark.asyncio()
    async def test_async_on_invoke(self, sm_runner):
        """Async on_invoke_<state> works correctly."""
        if not sm_runner.is_async:
            pytest.skip("Async-only test")

        invoked = []

        class Parent(StateChart):
            active = State(initial=True)
            completed = State(final=True)

            done_invoke_active = active.to(completed)

            async def on_invoke_active(self, **kwargs):
                await asyncio.sleep(0.01)
                invoked.append(True)
                return {"async_result": True}

        sm = await sm_runner.start(Parent)
        reached = await _wait_for(sm_runner, sm, "completed")
        assert reached, f"Parent did not reach 'completed'. Config: {sm.configuration_values}"
        assert len(invoked) > 0, "async on_invoke_active was not called"
