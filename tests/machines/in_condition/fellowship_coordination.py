from statemachine import State
from statemachine import StateChart


class FellowshipCoordination(StateChart):
    class mission(State.Parallel):
        class scouts(State.Compound):
            scouting = State(initial=True)
            reported = State(final=True)

            report = scouting.to(reported)

        class army(State.Compound):
            waiting = State(initial=True)
            marching = State(final=True)

            # Army marches only after scouts report
            waiting.to(marching, cond="In('reported')")
