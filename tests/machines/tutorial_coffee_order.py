from statemachine import State
from statemachine import StateChart


class CoffeeOrder(StateChart):
    pending = State(initial=True)
    preparing = State()
    ready = State()
    picked_up = State(final=True)

    start = pending.to(preparing)
    finish = preparing.to(ready)
    pick_up = ready.to(picked_up)
