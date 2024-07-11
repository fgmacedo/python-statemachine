"""
Async without external loop
===========================

Demonstrates that the state machine can have async callbacks even if the calling context
is synchronous.

"""

from statemachine import State
from statemachine import StateMachine


class AsyncStateMachine(StateMachine):
    initial = State("Initial", initial=True)
    processing = State()
    final = State("Final", final=True)

    start = initial.to(processing)
    finish = processing.to(final)

    async def on_start(self):
        return "starting"

    async def on_finish(self):
        return "finishing"


# %%
# Executing
# ---------


def sync_main():
    sm = AsyncStateMachine()
    result = sm.start()
    print(f"Start result is {result}")
    result = sm.send("finish")
    print(f"Finish result is {result}")
    print(sm.current_state)
    assert sm.current_state == sm.final


if __name__ == "__main__":
    sync_main()
