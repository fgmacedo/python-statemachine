from statemachine import State
from statemachine import StateChart


class CombinedGuard(StateChart):
    class positions(State.Parallel):
        class scout(State.Compound):
            out = State(initial=True)
            back = State(final=True)

            return_scout = out.to(back)

        class warrior(State.Compound):
            idle = State(initial=True)
            attacking = State(final=True)

            # Only attacks when scout is back
            charge = idle.to(attacking, cond="In('back')")
