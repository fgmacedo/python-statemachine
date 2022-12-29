# type: ignore

from statemachine import StateMachine, State


class TrafficLightMachine(StateMachine):
    "A traffic light machine"
    green = State("Green", initial=True)
    yellow = State("Yellow")
    red = State("Red")

    cycle = green.to(yellow) | yellow.to(red) | red.to(green)

    def on_cycle(self, *args, **kwargs):
        if args or kwargs:
            return args, kwargs
