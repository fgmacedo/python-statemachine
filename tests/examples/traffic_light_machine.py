"""
Traffic light machine
---------------------

Demonstrates the concept of ``cycle`` states.

"""
from statemachine import State
from statemachine import StateMachine


class TrafficLightMachine(StateMachine):
    "A traffic light machine"
    green = State(initial=True)
    yellow = State()
    red = State()

    cycle = green.to(yellow) | yellow.to(red) | red.to(green)

    def on_cycle(self, event_data):
        return f"Running {event_data.event} from {event_data.source.id} to {event_data.target.id}"
