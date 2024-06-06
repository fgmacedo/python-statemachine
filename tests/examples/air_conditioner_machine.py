"""
Air Conditioner machine
=======================

A StateMachine that exercises reading from a stream of events.

"""

import random

from statemachine import State
from statemachine import StateMachine
from statemachine.utils import run_async_from_sync


def sensor_temperature_reader(seed: int, lower: int = 15, higher: int = 35):
    "Infinitely generates random temperature readings."
    random.seed(seed)
    while True:
        yield random.randint(lower, higher)


class AirConditioner(StateMachine):
    off = State(initial=True)
    cooling = State()
    standby = State()

    sensor_updated = (
        off.to(cooling, cond="is_hot")
        | cooling.to(standby, cond="is_good")
        | standby.to(cooling, cond="is_hot")
        | standby.to(off, cond="is_cool")
        | off.to.itself(internal=True)
        | cooling.to.itself(internal=True)
        | standby.to.itself(internal=True)
    )

    async def is_hot(self, temperature: int):
        return temperature > 25

    async def is_good(self, temperature: int):
        return temperature < 20

    async def is_cool(self, temperature: int):
        return temperature < 18

    async def after_transition(self, event: str, source: State, target: State, event_data):
        print(f"Running {event} from {source!s} to {target!s}: {event_data.trigger_data.kwargs!r}")


# %%
# Testing


async def main():
    sensor = sensor_temperature_reader(123456)
    print("Will create AirConditioner machine")
    sm = AirConditioner()

    generator = (("sensor_updated", next(sensor)) for _ in range(20))
    for event, temperature in generator:
        await sm.send(event, temperature=temperature)


if __name__ == "__main__":
    # using `run_async_from_sync` to better integration with an already running loop.
    # on real life you should use `asyncio.run(main())`
    run_async_from_sync(main())
