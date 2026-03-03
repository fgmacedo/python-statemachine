from statemachine import State
from statemachine import StateChart


class MiddleEarthJourneyTwoCompounds(StateChart):
    class rivendell(State.Compound):
        council = State(initial=True)
        preparing = State()

        get_ready = council.to(preparing)

    class moria(State.Compound):
        gates = State(initial=True)
        bridge = State(final=True)

        cross = gates.to(bridge)

    march_to_moria = rivendell.to(moria)
