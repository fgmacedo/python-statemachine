import threading
import time

from statemachine.state import State
from statemachine.statemachine import StateChart


def test_machine_should_allow_multi_thread_event_changes():
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """

    class CampaignMachine(StateChart):
        "A workflow machine"

        draft = State(initial=True)
        producing = State()
        closed = State(final=True)
        add_job = draft.to(producing) | producing.to(closed)

    machine = CampaignMachine()

    def off_thread_change_state():
        time.sleep(0.01)
        machine.add_job()

    thread = threading.Thread(target=off_thread_change_state)
    thread.start()
    thread.join()
    assert machine.current_state_value == "producing"


def test_regression_443():
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """
    total_iterations = 4
    send_at_iteration = 3  # 0-indexed: send before the 4th sample

    class TrafficLightMachine(StateChart):
        "A traffic light machine"

        green = State(initial=True)
        yellow = State()
        red = State()

        cycle = green.to(yellow) | yellow.to(red) | red.to(green)

    class Controller:
        def __init__(self):
            self.statuses_history = []
            self.fsm = TrafficLightMachine()
            # set up thread
            self.thread = threading.Thread(target=self.recv_cmds)
            self.thread.start()

        def recv_cmds(self):
            """Pretend we receive a command triggering a state change."""
            for i in range(total_iterations):
                if i == send_at_iteration:
                    self.fsm.cycle()
                self.statuses_history.append(self.fsm.current_state_value)

    c1 = Controller()
    c2 = Controller()
    c1.thread.join()
    c2.thread.join()
    assert c1.statuses_history == ["green", "green", "green", "yellow"]
    assert c2.statuses_history == ["green", "green", "green", "yellow"]


def test_regression_443_with_modifications():
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """
    total_iterations = 4
    send_at_iteration = 3  # 0-indexed: send before the 4th sample

    class TrafficLightMachine(StateChart):
        "A traffic light machine"

        green = State(initial=True)
        yellow = State()
        red = State()

        cycle = green.to(yellow) | yellow.to(red) | red.to(green)

        def __init__(self, name):
            self.name = name
            self.statuses_history = []
            super().__init__()

        def beat(self):
            for i in range(total_iterations):
                if i == send_at_iteration:
                    self.cycle()
                self.statuses_history.append(f"{self.name}.{self.current_state_value}")

    class Controller:
        def __init__(self, name):
            self.fsm = TrafficLightMachine(name)
            # set up thread
            self.thread = threading.Thread(target=self.fsm.beat)
            self.thread.start()

    c1 = Controller("c1")
    c2 = Controller("c2")
    c3 = Controller("c3")
    c1.thread.join()
    c2.thread.join()
    c3.thread.join()

    assert c1.fsm.statuses_history == ["c1.green", "c1.green", "c1.green", "c1.yellow"]
    assert c2.fsm.statuses_history == ["c2.green", "c2.green", "c2.green", "c2.yellow"]
    assert c3.fsm.statuses_history == ["c3.green", "c3.green", "c3.green", "c3.yellow"]


async def test_regression_443_with_modifications_for_async_engine():
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """
    total_iterations = 4
    send_at_iteration = 3  # 0-indexed: send before the 4th sample

    class TrafficLightMachine(StateChart):
        "A traffic light machine"

        green = State(initial=True)
        yellow = State()
        red = State()

        cycle = green.to(yellow) | yellow.to(red) | red.to(green)

        async def on_cycle(self):
            return "caution"

        def __init__(self, name):
            self.name = name
            self.statuses_history = []
            super().__init__()

        def beat(self):
            for i in range(total_iterations):
                if i == send_at_iteration:
                    self.cycle()
                self.statuses_history.append(f"{self.name}.{self.current_state_value}")

    class Controller:
        def __init__(self, name):
            self.fsm = TrafficLightMachine(name)

        async def start(self):
            # set up thread
            await self.fsm.activate_initial_state()
            self.thread = threading.Thread(target=self.fsm.beat)
            self.thread.start()

    c1 = Controller("c1")
    c2 = Controller("c2")
    c3 = Controller("c3")
    await c1.start()
    await c2.start()
    await c3.start()
    c1.thread.join()
    c2.thread.join()
    c3.thread.join()

    assert c1.fsm.statuses_history == ["c1.green", "c1.green", "c1.green", "c1.yellow"]
    assert c2.fsm.statuses_history == ["c2.green", "c2.green", "c2.green", "c2.yellow"]
    assert c3.fsm.statuses_history == ["c3.green", "c3.green", "c3.green", "c3.yellow"]
