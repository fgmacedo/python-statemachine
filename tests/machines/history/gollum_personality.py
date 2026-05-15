from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart


class GollumPersonality(StateChart):
    class personality(State.Compound):
        smeagol = State(initial=True)
        gollum = State()
        h = HistoryState()

        dark_side = smeagol.to(gollum)
        light_side = gollum.to(smeagol)

    outside = State()
    leave = personality.to(outside)
    return_via_history = outside.to(personality.h)
