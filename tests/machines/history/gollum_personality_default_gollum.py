from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart


class GollumPersonalityDefaultGollum(StateChart):
    class personality(State.Compound):
        smeagol = State(initial=True)
        gollum = State()
        h = HistoryState()

        dark_side = smeagol.to(gollum)
        _ = h.to(gollum)  # default: gollum (not the initial smeagol)

    outside = State(initial=True)
    enter_via_history = outside.to(personality.h)
    leave = personality.to(outside)
