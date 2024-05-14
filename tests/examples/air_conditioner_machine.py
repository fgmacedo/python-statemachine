"""
Air Conditioner machine
=======================

A StateMachine that exercises reading from a stream of events.

"""

import doctest
import random

from statemachine import State
from statemachine import StateMachine


def sensor_temperature_reader(seed: int, lower: int = 15, higher: int = 35):
    "Infinitely generates random temperature readings."
    random.seed(seed)
    while True:
        yield random.randint(lower, higher)


class AirConditioner(StateMachine):
    """
    >>> sensor = sensor_temperature_reader(123456)
    >>> sm = AirConditioner()
    >>> for i in range(20):
    ...    temperature = next(sensor)
    ...    sm.send("sensor_updated", temperature=temperature)
    Running sensor_updated from Off to Off: {'temperature': 24}
    Running sensor_updated from Off to Off: {'temperature': 15}
    Running sensor_updated from Off to Off: {'temperature': 20}
    Running sensor_updated from Off to Off: {'temperature': 15}
    Running sensor_updated from Off to Off: {'temperature': 17}
    Running sensor_updated from Off to Off: {'temperature': 16}
    Running sensor_updated from Off to Off: {'temperature': 23}
    Running sensor_updated from Off to Off: {'temperature': 15}
    Running sensor_updated from Off to Off: {'temperature': 18}
    Running sensor_updated from Off to Off: {'temperature': 22}
    Running sensor_updated from Off to Cooling: {'temperature': 35}
    Running sensor_updated from Cooling to Cooling: {'temperature': 30}
    Running sensor_updated from Cooling to Cooling: {'temperature': 20}
    Running sensor_updated from Cooling to Standby: {'temperature': 15}
    Running sensor_updated from Standby to Cooling: {'temperature': 31}
    Running sensor_updated from Cooling to Standby: {'temperature': 19}
    Running sensor_updated from Standby to Cooling: {'temperature': 27}
    Running sensor_updated from Cooling to Cooling: {'temperature': 35}
    Running sensor_updated from Cooling to Cooling: {'temperature': 26}
    Running sensor_updated from Cooling to Standby: {'temperature': 16}

    """

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

    def is_hot(self, temperature: int):
        return temperature > 25

    def is_good(self, temperature: int):
        return temperature < 20

    def is_cool(self, temperature: int):
        return temperature < 18

    def after_transition(self, event: str, source: State, target: State, event_data):
        print(f"Running {event} from {source!s} to {target!s}: {event_data.trigger_data.kwargs!r}")


doctest.testmod()
