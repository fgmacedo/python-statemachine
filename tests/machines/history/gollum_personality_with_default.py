from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart


class GollumPersonalityWithDefault(StateChart):
    class personality(State.Compound):
        smeagol = State(initial=True)
        gollum = State()
        h = HistoryState()

        dark_side = smeagol.to(gollum)
        _ = h.to(smeagol)  # default: smeagol

    outside = State(initial=True)
    enter_via_history = outside.to(personality.h)
    leave = personality.to(outside)
