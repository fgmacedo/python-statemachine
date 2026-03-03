from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart


class DeepHistorySC(StateChart):
    class outer(State.Compound, name="Outer"):
        class inner(State.Compound, name="Inner"):
            a = State(initial=True)
            b = State()
            go = a.to(b)

        start = State(initial=True)
        enter_inner = start.to(inner)
        h = HistoryState(type="deep")

    away = State(initial=True)

    dive = away.to(outer)
    leave = outer.to(away)
    restore = away.to(outer.h)
