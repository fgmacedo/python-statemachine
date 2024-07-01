import threading
import time

from statemachine.state import State
from statemachine.statemachine import StateMachine


def test_machine_should_allow_multi_thread_event_changes():
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """

    class CampaignMachine(StateMachine):
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
    assert machine.current_state.id == "producing"


def test_regression_443():
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """
    time_collecting = 0.2
    time_to_send = 0.125
    time_sampling_current_state = 0.05

    class TrafficLightMachine(StateMachine):
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
            t = threading.Thread(target=self.recv_cmds)
            t.start()

        def recv_cmds(self):
            """Pretend we receive a command triggering a state change after Xs."""
            waiting_time = 0
            sent = False
            while waiting_time < time_collecting:
                if waiting_time >= time_to_send and not sent:
                    self.fsm.cycle()
                    sent = True

                waiting_time += time_sampling_current_state
                self.statuses_history.append(self.fsm.current_state.id)
                time.sleep(time_sampling_current_state)

    c1 = Controller()
    c2 = Controller()
    time.sleep(time_collecting + 0.01)
    assert c1.statuses_history == ["green", "green", "green", "yellow"]
    assert c2.statuses_history == ["green", "green", "green", "yellow"]


def test_regression_443_with_modifications():
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """
    time_collecting = 0.2
    time_to_send = 0.125
    time_sampling_current_state = 0.05

    class TrafficLightMachine(StateMachine):
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
            waiting_time = 0
            sent = False
            while waiting_time < time_collecting:
                if waiting_time >= time_to_send and not sent:
                    self.cycle()
                    sent = True

                self.statuses_history.append(f"{self.name}.{self.current_state.id}")

                time.sleep(time_sampling_current_state)
                waiting_time += time_sampling_current_state

    class Controller:
        def __init__(self, name):
            self.fsm = TrafficLightMachine(name)
            # set up thread
            t = threading.Thread(target=self.fsm.beat)
            t.start()

    c1 = Controller("c1")
    c2 = Controller("c2")
    c3 = Controller("c3")
    time.sleep(time_collecting + 0.01)

    assert c1.fsm.statuses_history == ["c1.green", "c1.green", "c1.green", "c1.yellow"]
    assert c2.fsm.statuses_history == ["c2.green", "c2.green", "c2.green", "c2.yellow"]
    assert c3.fsm.statuses_history == ["c3.green", "c3.green", "c3.green", "c3.yellow"]


async def test_regression_443_with_modifications_for_async_engine():  # noqa: C901
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """
    time_collecting = 0.2
    time_to_send = 0.125
    time_sampling_current_state = 0.05

    class TrafficLightMachine(StateMachine):
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
            waiting_time = 0
            sent = False
            while waiting_time < time_collecting:
                if waiting_time >= time_to_send and not sent:
                    self.cycle()
                    sent = True

                self.statuses_history.append(f"{self.name}.{self.current_state.id}")

                time.sleep(time_sampling_current_state)
                waiting_time += time_sampling_current_state

    class Controller:
        def __init__(self, name):
            self.fsm = TrafficLightMachine(name)

        async def start(self):
            # set up thread
            await self.fsm.activate_initial_state()
            t = threading.Thread(target=self.fsm.beat)
            t.start()

    c1 = Controller("c1")
    c2 = Controller("c2")
    c3 = Controller("c3")
    await c1.start()
    await c2.start()
    await c3.start()
    time.sleep(time_collecting + 0.01)

    assert c1.fsm.statuses_history == ["c1.green", "c1.green", "c1.green", "c1.yellow"]
    assert c2.fsm.statuses_history == ["c2.green", "c2.green", "c2.green", "c2.yellow"]
    assert c3.fsm.statuses_history == ["c3.green", "c3.green", "c3.green", "c3.yellow"]
