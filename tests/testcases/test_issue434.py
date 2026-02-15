from time import sleep

import pytest

from statemachine import State
from statemachine import StateChart


class Model:
    def __init__(self, data: dict):
        self.data = data


class DataCheckerMachine(StateChart):
    error_on_execution = False

    check_data = State(initial=True)
    data_good = State(final=True)
    data_bad = State(final=True)

    MAX_CYCLE_COUNT = 10
    cycle_count = 0

    cycle = (
        check_data.to(data_good, cond="data_looks_good")
        | check_data.to(data_bad, cond="max_cycle_reached")
        | check_data.to.itself(internal=True)
    )

    def data_looks_good(self):
        return self.model.data.get("value") > 10.0

    def max_cycle_reached(self):
        return self.cycle_count > self.MAX_CYCLE_COUNT

    def after_cycle(self, event: str, source: State, target: State):
        print(f"Running {event} {self.cycle_count} from {source!s} to {target!s}.")
        self.cycle_count += 1


@pytest.fixture()
def initial_data():
    return {"value": 1}


@pytest.fixture()
def data_checker_machine(initial_data):
    return DataCheckerMachine(Model(initial_data))


def test_max_cycle_without_success(data_checker_machine):
    sm = data_checker_machine
    cycle_rate = 0.1

    while not sm.is_terminated:
        sm.cycle()
        sleep(cycle_rate)

    assert sm.data_bad.is_active
    assert sm.cycle_count == 12


def test_data_turns_good_mid_cycle(initial_data):
    sm = DataCheckerMachine(Model(initial_data))
    cycle_rate = 0.1

    while not sm.is_terminated:
        sm.cycle()
        if sm.cycle_count == 5:
            print("Now data looks good!")
            sm.model.data["value"] = 20
        sleep(cycle_rate)

    assert sm.data_good.is_active
    assert sm.cycle_count == 6  # Transition occurs at the 6th cycle
