from statemachine import State
from statemachine import StateChart


class MiddleEarthJourneyWithFinals(StateChart):
    class rivendell(State.Compound):
        council = State(initial=True)
        preparing = State(final=True)

        get_ready = council.to(preparing)

    class moria(State.Compound):
        gates = State(initial=True)
        bridge = State(final=True)

        cross = gates.to(bridge)

    class lothlorien(State.Compound):
        mirror = State(initial=True)
        departure = State(final=True)

        leave = mirror.to(departure)

    march_to_moria = rivendell.to(moria)
    march_to_lorien = moria.to(lothlorien)
