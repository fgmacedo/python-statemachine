from statemachine import State
from statemachine import StateChart


class QuestForErebor(StateChart):
    class lonely_mountain(State.Compound):
        approach = State(initial=True)
        inside = State(final=True)

        enter_mountain = approach.to(inside)

    victory = State(final=True)
    done_state_lonely_mountain = lonely_mountain.to(victory)
