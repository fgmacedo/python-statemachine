from statemachine import State
from statemachine import StateChart


class QuestForEreborDoneConvention(StateChart):
    class quest(State.Compound):
        traveling = State(initial=True)
        arrived = State(final=True)

        finish = traveling.to(arrived)

    celebration = State(final=True)
    done_state_quest = quest.to(celebration)
