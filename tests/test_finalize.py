import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.transition import Transition


class TrafficLightMachine(StateMachine):
    """A simple traffic light state machine for testing."""

    red = State("Red", initial=True)
    yellow = State("Yellow")
    green = State("Green")

    cycle = red.to(green) | green.to(yellow) | yellow.to(red)


class AsyncTrafficLightMachine(TrafficLightMachine):
    """Traffic light with async callbacks."""

    async def before_cycle(self):
        # Makes this an async state machine
        pass


# Basic finalize functionality tests
def test_sync_finalize_basic():
    """Test basic finalize action in sync mode."""
    calls = []

    class TestMachine(TrafficLightMachine):
        def finalize(self, state):
            calls.append(("finalize", state.id))

    sm = TestMachine()
    assert sm.current_state == sm.red
    sm.cycle()  # red -> green
    assert sm.current_state == sm.green
    assert calls == [("finalize", "green")]

    sm.cycle()  # green -> yellow
    assert sm.current_state == sm.yellow
    assert calls == [("finalize", "green"), ("finalize", "yellow")]


# Error handling tests
def test_sync_finalize_with_error():
    """Test finalize action when transition fails."""
    calls = []

    class FailingTrafficLight(TrafficLightMachine):
        def before_cycle(self):
            raise ValueError("Simulated failure")

        def finalize(self, state):
            calls.append(("finalize", state.id))

    sm = FailingTrafficLight()

    assert sm.current_state == sm.red
    with pytest.raises(ValueError):  # noqa: PT011
        sm.cycle()

    assert sm.current_state == sm.red  # State unchanged due to error
    assert calls == [("finalize", "red")]  # Finalize still called


def test_sync_finalize_error_propagation():
    """Test that finalize errors are logged but don't affect state machine operation."""
    calls = []

    class TestMachine(TrafficLightMachine):
        def finalize(self, state):
            calls.append("failing")
            raise ValueError("Simulated failure")

    sm = TestMachine()
    sm.cycle()  # Should complete despite finalize error
    assert calls == ["failing"]
    assert sm.current_state == sm.green


# Full dependency injection tests
def test_sync_finalize_dependency_injection():
    """Test that finalize method supports dependency injection."""
    results = {}

    class TestMachine(TrafficLightMachine):
        def finalize(
            self,
            message,
            event,
            source,
            target,
            state,
            model,
            transition,
            *args,
            **kwargs,
        ):
            results.update(
                {
                    "message": message,
                    "event": event,
                    "source": source.id,
                    "target": target.id,
                    "current_state": state.id,
                    "model": model,
                    "transition": transition,
                    "args": args,
                    "kwargs": kwargs,
                }
            )

    sm = TestMachine()
    sm.cycle(123, message="test")  # Pass some args and kwargs
    # Verify all injected parameters
    assert results["event"] == "cycle"
    assert results["source"] == "red"
    assert results["target"] == "green"
    assert results["current_state"] == "green"
    assert results["model"] is sm.model
    assert isinstance(results["transition"], Transition)
    assert results["kwargs"]["event_data"].args == (123,)
    assert results["message"] == "test"


def test_callback_ordering():
    """Test that callbacks are executed in the correct order."""
    execution_order = []

    class OrderedCallbackMachine(StateMachine):
        state1 = State("State1", initial=True)
        state2 = State("State2")

        transition = state1.to(state2)

        def before_transition(self):
            execution_order.append("before")

        def on_exit_state1(self):
            execution_order.append("exit")

        def on_transition(self):
            execution_order.append("on")

        def on_enter_state2(self):
            execution_order.append("enter")

        def after_transition(self):
            execution_order.append("after")

        def finalize(self):
            execution_order.append("finalize")

    sm = OrderedCallbackMachine()
    sm.transition()

    assert execution_order == [
        "before",
        "exit",
        "on",
        "enter",
        "after",
        "finalize",
    ], "validate run ordering"


###### Async tests ######


@pytest.mark.asyncio()
async def test_async_finalize_basic():
    """Test basic finalize action in async mode."""
    calls = []

    class TestMachine(AsyncTrafficLightMachine):
        async def finalize(self, state):
            calls.append(("finalize", state.id))

    sm = TestMachine()
    await sm.activate_initial_state()

    assert sm.current_state == sm.red
    await sm.cycle()  # red -> green
    assert sm.current_state == sm.green
    assert calls == [("finalize", "green")]

    await sm.cycle()  # green -> yellow
    assert sm.current_state == sm.yellow
    assert calls == [("finalize", "green"), ("finalize", "yellow")]


@pytest.mark.asyncio()
async def test_async_finalize_with_error():
    """Test finalize action when async transition fails."""
    calls = []

    class AsyncFailingTrafficLight(AsyncTrafficLightMachine):
        async def before_cycle(self):
            raise ValueError("Simulated async failure")

        async def finalize(self, state):
            calls.append(("finalize", state.id))

    sm = AsyncFailingTrafficLight()
    await sm.activate_initial_state()

    assert sm.current_state == sm.red
    with pytest.raises(ValueError):  # noqa: PT011
        await sm.cycle()

    assert sm.current_state == sm.red  # State unchanged due to error
    assert calls == [("finalize", "red")]  # Finalize still called


@pytest.mark.asyncio()
async def test_async_finalize_with_async_error():
    """Test that async finalize errors are properly handled."""
    calls = []

    class TestMachine(AsyncTrafficLightMachine):
        async def finalize(self, state):
            calls.append(("before_error", state.id))
            raise ValueError("Simulated async error")

    sm = TestMachine()
    await sm.activate_initial_state()

    assert sm.current_state == sm.red
    await sm.cycle()  # Should complete despite async finalize error
    assert sm.current_state == sm.green
    assert calls == [("before_error", "green")]


@pytest.mark.asyncio()
async def test_async_finalize_with_dependency_injection():
    """Test that async finalize supports dependency injection."""
    results = {}

    class TestMachine(AsyncTrafficLightMachine):
        async def finalize(
            self,
            message,
            event,
            source,
            target,
            state,
            model,
            transition,
            *args,
            **kwargs,
        ):
            results.update(
                {
                    "message": message,
                    "event": event,
                    "source": source.id,
                    "target": target.id,
                    "current_state": state.id,
                    "model": model,
                    "transition": transition,
                    "args": args,
                    "kwargs": kwargs,
                }
            )

    sm = TestMachine()
    await sm.activate_initial_state()
    await sm.cycle(123, message="test")  # Pass some args and kwargs

    # Verify all injected parameters
    assert results["event"] == "cycle"
    assert results["source"] == "red"
    assert results["target"] == "green"
    assert results["current_state"] == "green"
    assert results["model"] is sm.model
    assert isinstance(results["transition"], Transition)
    assert results["kwargs"]["event_data"].args == (123,)
    assert results["message"] == "test"


@pytest.mark.asyncio()
async def test_async_callback_ordering():
    """Test that callbacks are executed in the correct order in async mode."""
    execution_order = []

    class AsyncOrderedCallbackMachine(StateMachine):
        state1 = State("State1", initial=True)
        state2 = State("State2")

        transition = state1.to(state2)

        async def before_transition(self):
            execution_order.append("before")

        async def on_exit_state1(self):
            execution_order.append("exit")

        async def on_transition(self):
            execution_order.append("on")

        async def on_enter_state2(self):
            execution_order.append("enter")

        async def after_transition(self):
            execution_order.append("after")

        async def finalize(self):
            execution_order.append("finalize")

    sm = AsyncOrderedCallbackMachine()
    await sm.activate_initial_state()
    await sm.transition()

    assert execution_order == [
        "before",
        "exit",
        "on",
        "enter",
        "after",
        "finalize",
    ], "validate run ordering"
