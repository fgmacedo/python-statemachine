from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart


class ShallowMoria(StateChart):
    class moria(State.Compound):
        class halls(State.Compound):
            entrance = State(initial=True)
            chamber = State()

            explore = entrance.to(chamber)

        assert isinstance(halls, State)
        h = HistoryState()
        bridge = State(final=True)
        flee = halls.to(bridge)

    outside = State()
    escape = moria.to(outside)
    return_shallow = outside.to(moria.h)  # type: ignore[has-type]
