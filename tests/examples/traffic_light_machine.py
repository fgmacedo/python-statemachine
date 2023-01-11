"""
Traffic light machine
---------------------

Demonstrates the concept of ``cycle`` states.

"""
from statemachine import State
from statemachine import StateMachine


class TrafficLightMachine(StateMachine):
    "A traffic light machine"
    green = State("Green", initial=True)
    yellow = State("Yellow")
    red = State("Red")

    cycle = green.to(yellow) | yellow.to(red) | red.to(green)

    def on_cycle(self, event_data=None):
        return "Running {} from {} to {}".format(
            event_data.event,
            event_data.source.id,
            event_data.target.id,
        )
