from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart


class HistorySC(StateChart):
    class process(State.Compound, name="Process"):
        step1 = State(initial=True)
        step2 = State()
        advance = step1.to(step2)
        h = HistoryState()

    paused = State(initial=True)

    pause = process.to(paused)
    resume = paused.to(process.h)
    begin = paused.to(process)
