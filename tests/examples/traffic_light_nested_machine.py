"""
Nested Traffic light machine
----------------------------

Demonstrates the concept of nested compound states.

From this example on XState: https://xstate.js.org/docs/guides/hierarchical.html#api

"""
import time

from statemachine import State
from statemachine import StateMachine


class NestedTrafficLightMachine(StateMachine):
    "A traffic light machine"
    green = State(initial=True, enter="reset_elapsed")
    yellow = State(enter="reset_elapsed")

    class red(State.Builder, enter="reset_elapsed"):
        "Pedestrian states"
        walk = State(initial=True)
        wait = State()
        stop = State()
        blinking = State()

        ped_countdown = walk.to(wait) | wait.to(stop)

    timer = green.to(yellow) | yellow.to(red) | red.to(green)
    power_outage = red.blinking.from_()
    power_restored = red.from_()

    def __init__(self, seconds_to_turn_state=5, seconds_running=20):
        self.seconds_to_turn_state = seconds_to_turn_state
        self.seconds_running = seconds_running
        super().__init__(allow_event_without_transition=True)

    def on_timer(self, event: str, source: State, target: State):
        print(f".. Running {event} from {source.id} to {target.id}")

    def reset_elapsed(self, event: str, time: int = 0):
        print(f"entering reset_elapsed from {event} with {time}")
        self.last_turn = time

    @timer.cond
    def time_is_over(self, time):
        return time - self.last_turn > self.seconds_to_turn_state

    def run_forever(self):
        self.running = True
        start_time = time.time()
        while self.running:
            print("tick!")
            time.sleep(1)
            curr_time = time.time()
            self.send("timer", time=curr_time)

            if curr_time - start_time > self.seconds_running:
                self.running = False


sm = NestedTrafficLightMachine()
sm.send("anything")
