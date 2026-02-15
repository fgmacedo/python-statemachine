"""

### Issue 509

A StateChart that exercises the example given on issue
#[509](https://github.com/fgmacedo/python-statemachine/issues/509).

When multiple async coroutines send events concurrently, each caller should
receive its own event's result or exception — not another caller's.

Original problem: fn2 triggers a validator exception, but fn1 receives it instead.
"""

import asyncio

import pytest

from statemachine import State
from statemachine import StateChart


class Issue509SC(StateChart):
    error_on_execution = False

    INITIAL = State(initial=True)
    FINAL = State()

    noop = INITIAL.to(FINAL, on="do_nothing")
    noop2 = INITIAL.to(FINAL, on="do_nothing", validators="raise_exception") | FINAL.to.itself(
        on="do_nothing", validators="raise_exception"
    )

    async def do_nothing(self, name):
        await asyncio.sleep(0.1)
        return f"Did nothing via {name}"

    def raise_exception(self):
        raise ValueError("noop2 is not allowed")


@pytest.mark.asyncio()
async def test_issue509_exception_routed_to_correct_caller():
    test = Issue509SC()
    await test.activate_initial_state()

    results = {}

    async def fn1():
        results["fn1"] = await test.send("noop", "fn1")

    async def fn2():
        try:
            await test.send("noop2", "fn2")
            results["fn2"] = "no error"
        except ValueError as e:
            results["fn2"] = f"caught: {e}"

    task1 = asyncio.create_task(fn1())
    task2 = asyncio.create_task(fn2())
    await asyncio.gather(task1, task2)

    # fn1 should get its own result, not fn2's exception
    assert results["fn1"] == "Did nothing via fn1"
    # fn2 should catch the ValueError from its own validator
    assert results["fn2"] == "caught: noop2 is not allowed"
