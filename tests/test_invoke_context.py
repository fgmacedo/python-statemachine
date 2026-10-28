import asyncio
from contextvars import ContextVar

import pytest
from statemachine.engines.base import _processing_step
from statemachine.engines.base import _running_engine

from statemachine import State
from statemachine import StateChart


@pytest.mark.parametrize("sm_runner", ["async"], indirect=True)
async def test_async_invoke_waits_for_raised_event(sm_runner):
    start = asyncio.Event()
    attempted = asyncio.Event()
    returned = asyncio.Event()
    busy_entered = asyncio.Event()
    release_busy = asyncio.Event()
    release_worker = asyncio.Event()
    request_id = ContextVar("request_id", default=None)
    trace = []
    contexts = []

    async def worker(machine):
        contexts.append(request_id.get())
        await start.wait()
        attempted.set()
        await machine.raise_("tick")
        contexts.append(request_id.get())
        trace.append("invoke_returned")
        returned.set()
        await release_worker.wait()

    class Machine(StateChart):
        active = State(initial=True, invoke=worker)
        busy = active.to(None)
        tick = active.to(None)

        async def on_busy(self):
            busy_entered.set()
            await release_busy.wait()
            trace.append("busy_completed")

        def on_tick(self):
            trace.append("tick")

    token = request_id.set("request")
    machine = await sm_runner.start(Machine)
    busy_task = asyncio.create_task(machine.send("busy"))
    try:
        await asyncio.wait_for(busy_entered.wait(), timeout=1)
        start.set()
        await asyncio.wait_for(attempted.wait(), timeout=1)
        premature = returned.is_set()
        release_busy.set()
        await asyncio.wait_for(busy_task, timeout=1)
        await asyncio.wait_for(returned.wait(), timeout=1)

        assert not premature
        assert trace == ["busy_completed", "tick", "invoke_returned"]
        assert contexts == ["request", "request"]
        assert request_id.get() == "request"
        assert _running_engine.get() is None
    finally:
        release_busy.set()
        release_worker.set()
        tasks = [inv.task for inv in machine._engine._invoke_manager._active.values() if inv.task]
        machine._engine.stop()
        await asyncio.gather(busy_task, *tasks, return_exceptions=True)
        request_id.reset(token)


@pytest.mark.parametrize("sm_runner", ["async"], indirect=True)
async def test_async_invoke_restores_context_when_task_factory_raises(sm_runner):
    release = asyncio.Event()
    observed = []

    async def worker():
        await release.wait()

    class Machine(StateChart):
        active = State(initial=True, invoke=worker)
        tick = active.to(None)

    machine = await sm_runner.start(Machine)
    manager = machine._engine._invoke_manager
    loop = asyncio.get_running_loop()
    original_factory = loop.get_task_factory()

    def failing_factory(loop, coroutine, **kwargs):
        observed.append(_running_engine.get())
        coroutine.close()
        raise RuntimeError("cannot create invoke task")

    try:
        manager.mark_for_invoke(Machine.active)
        loop.set_task_factory(failing_factory)
        with _processing_step(machine._engine):
            with pytest.raises(RuntimeError, match="cannot create invoke task"):
                await manager.spawn_pending_async()
            assert _running_engine.get() is machine._engine
        assert _running_engine.get() is None
        assert observed == [None]
    finally:
        loop.set_task_factory(original_factory)
        release.set()
        tasks = [inv.task for inv in manager._active.values() if inv.task]
        machine._engine.stop()
        await asyncio.gather(*tasks, return_exceptions=True)
