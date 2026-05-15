from statemachine import State
from statemachine import StateChart


class EventlessIn(StateChart):
    class coordination(State.Parallel):
        class leader(State.Compound):
            planning = State(initial=True)
            ready = State(final=True)

            get_ready = planning.to(ready)

        class follower(State.Compound):
            waiting = State(initial=True)
            moving = State(final=True)

            # Eventless: move when leader is ready
            waiting.to(moving, cond="In('ready')")
