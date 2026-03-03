from statemachine import State
from statemachine import StateChart


class MoriaExpedition(StateChart):
    class moria(State.Compound):
        class upper_halls(State.Compound):
            entrance = State(initial=True)
            bridge = State(final=True)

            cross = entrance.to(bridge)

        assert isinstance(upper_halls, State)
        depths = State(final=True)
        descend = upper_halls.to(depths)
