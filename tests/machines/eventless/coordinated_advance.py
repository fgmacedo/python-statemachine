from statemachine import State
from statemachine import StateChart


class CoordinatedAdvance(StateChart):
    class forces(State.Parallel):
        class vanguard(State.Compound):
            waiting = State(initial=True)
            advanced = State(final=True)

            move_forward = waiting.to(advanced)

        class rearguard(State.Compound):
            holding = State(initial=True)
            moved_up = State(final=True)

            # Eventless: advance only when vanguard has advanced
            holding.to(moved_up, cond="In('advanced')")
