"""Unit tests for the Python invoke API (State(invoke=...) and done_invoke_ convention)."""

import asyncio
import time

import pytest
from statemachine.invoke import InvokeConfig

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

    def test_invoke_class_becomes_invoke_config(self):
        s = State(invoke=ChildMachine)
        assert len(s.invocations) == 1
        assert isinstance(s.invocations[0], InvokeConfig)
        assert s.invocations[0].child_class is ChildMachine

    def test_invoke_config_passthrough(self):
        config = InvokeConfig(child_class=ChildMachine)
        s = State(invoke=config)
        assert len(s.invocations) == 1
        assert s.invocations[0] is config

    def test_invoke_list_of_classes(self):
        s = State(invoke=[ChildMachine, SlowChild])
        assert len(s.invocations) == 2
        assert s.invocations[0].child_class is ChildMachine
        assert s.invocations[1].child_class is SlowChild


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

        active = sm._engine.invoke_manager._active
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

        active_before = list(sm._engine.invoke_manager._active.values())
        assert len(active_before) > 0

        await sm_runner.send(sm, "abort")
        assert active_before[0].cancelled, "Child was not cancelled after exiting invoke state"


class TestMultipleInvocations:
    """Test invoking multiple children from the same state."""

    def test_multiple_invoke_configs(self):
        class Parent(StateChart):
            active = State(initial=True, invoke=[ChildMachine, ChildMachine])
            done = State(final=True)

            done_invoke_active = active.to(done)

        assert len(Parent.states_map["active"].invocations) == 2
