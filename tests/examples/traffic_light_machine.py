"""

---------------------
Traffic light machine
---------------------

This example demonstrates how to create a traffic light machine using the `statemachine` library.

The state machine will run in a dedicated thread and will cycle through the states.

"""

import time
from threading import Event as ThreadingEvent
from threading import Thread

from statemachine import State
from statemachine import StateMachine


class TrafficLightMachine(StateMachine):
    "A traffic light machine"

    green = State(initial=True)
    yellow = State()
    red = State()

    cycle = green.to(yellow) | yellow.to(red) | red.to(green)

    def before_cycle(self, event: str, source: State, target: State):
        print(f"Running {event} from {source.id} to {target.id}")


# %%
# Run in a dedicated thread


class Supervisor:
    def __init__(self, sm: StateMachine, sm_event: str):
        self.sm = sm
        self.sm_event = sm_event
        self.stop_event = ThreadingEvent()

    def run(self):
        while not self.stop_event.is_set():
            self.sm.send(self.sm_event)
            self.stop_event.wait(0.1)

    def stop(self):
        self.stop_event.set()


def main():
    supervisor = Supervisor(TrafficLightMachine(), "cycle")
    t = Thread(target=supervisor.run)
    t.start()

    time.sleep(0.5)
    supervisor.stop()
    t.join()


if __name__ == "__main__":
    main()
