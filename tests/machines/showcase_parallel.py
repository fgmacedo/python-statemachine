from statemachine import State
from statemachine import StateChart


class ParallelSC(StateChart):
    class both(State.Parallel, name="Both"):
        class left(State.Compound, name="Left"):
            l1 = State(initial=True)
            l2 = State(final=True)
            go_l = l1.to(l2)

        class right(State.Compound, name="Right"):
            r1 = State(initial=True)
            r2 = State(final=True)
            go_r = r1.to(r2)

    start = State(initial=True)
    end = State(final=True)

    enter = start.to(both)
    done_state_both = both.to(end)
