from statemachine import State
from statemachine import StateChart


class TwoTowers(StateChart):
    class battle(State.Parallel):
        class helms_deep(State.Compound):
            fighting = State(initial=True)
            victory = State(final=True)

            win = fighting.to(victory)

        class isengard(State.Compound):
            besieging = State(initial=True)
            flooded = State(final=True)

            flood = besieging.to(flooded)

    aftermath = State(final=True)
    done_state_battle = battle.to(aftermath)
