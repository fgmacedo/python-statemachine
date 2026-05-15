from statemachine import State
from statemachine import StateChart


class ReverseTrafficLightMachine(StateChart):
    "A traffic light machine"

    green = State(initial=True)
    yellow = State()
    red = State()

    stop = red.from_(yellow, green, red)
    cycle = green.from_(red) | yellow.from_(green) | red.from_(yellow) | red.from_.itself()
