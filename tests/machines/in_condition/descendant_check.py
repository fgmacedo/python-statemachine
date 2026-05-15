from statemachine import State
from statemachine import StateChart


class DescendantCheck(StateChart):
    class realm(State.Compound):
        village = State(initial=True)
        castle = State()

        ascend = village.to(castle)

    conquered = State(final=True)
    # Guarded by being inside the castle
    conquer = realm.to(conquered, cond="In('castle')")
    explore = realm.to.itself(internal=True)  # type: ignore[attr-defined]
