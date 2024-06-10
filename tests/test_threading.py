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
        closed = State()
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
    time_to_collect = 0.2
    time_to_send = 0.125
    time_to_collect_step = 0.05

    class TrafficLightMachine(StateMachine):
        "A traffic light machine"

        green = State(initial=True)
        yellow = State()
        red = State()

        cycle = green.to(yellow) | yellow.to(red) | red.to(green)

    class Controller:
        def __init__(self):
            self.fsm = TrafficLightMachine()
            # set up thread
            t = threading.Thread(target=self.recv_cmds)
            t.start()

        def recv_cmds(self):
            """Pretend we receive a command triggering a state change after Xs."""
            time.sleep(time_to_send)
            self.fsm.cycle()

        def collect_statuses(self):
            wait = time_to_collect
            while wait > 0:
                yield self.fsm.current_state.id
                time.sleep(time_to_collect_step)
                wait -= time_to_collect_step

    c = Controller()
    statuses = list(c.collect_statuses())
    assert statuses == ["green", "green", "green", "yellow", "yellow"]
