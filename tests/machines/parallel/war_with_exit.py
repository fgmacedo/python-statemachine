from statemachine import State
from statemachine import StateChart


class WarWithExit(StateChart):
    class war(State.Parallel):
        class front_a(State.Compound):
            fighting = State(initial=True)
            won = State(final=True)

            win_a = fighting.to(won)

        class front_b(State.Compound):
            holding = State(initial=True)
            held = State(final=True)

            hold_b = holding.to(held)

    peace = State(final=True)
    truce = war.to(peace)
