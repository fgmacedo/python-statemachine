from statemachine import State
from statemachine import StateChart


class AutoAdvance(StateChart):
    class journey(State.Compound):
        step1 = State(initial=True)
        step2 = State()
        step3 = State(final=True)

        step1.to(step2)
        step2.to(step3)

    done = State(final=True)
    done_state_journey = journey.to(done)
