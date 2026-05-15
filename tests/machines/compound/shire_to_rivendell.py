from statemachine import State
from statemachine import StateChart


class ShireToRivendell(StateChart):
    class shire(State.Compound):
        bag_end = State(initial=True)
        green_dragon = State()

        visit_pub = bag_end.to(green_dragon)

    road = State(final=True)
    depart = shire.to(road)
