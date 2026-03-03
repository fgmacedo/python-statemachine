from statemachine import State
from statemachine import StateChart


class BeaconChainLighting(StateChart):
    class chain(State.Compound):
        amon_din = State(initial=True)
        eilenach = State()
        nardol = State()
        halifirien = State(final=True)

        # Eventless chain: each fires immediately
        amon_din.to(eilenach)
        eilenach.to(nardol)
        nardol.to(halifirien)

    all_lit = State(final=True)
    done_state_chain = chain.to(all_lit)
