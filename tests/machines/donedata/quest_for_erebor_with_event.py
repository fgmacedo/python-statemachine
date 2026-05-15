from statemachine import Event
from statemachine import State
from statemachine import StateChart


class QuestForEreborWithEvent(StateChart):
    class quest(State.Compound):
        traveling = State(initial=True)
        arrived = State(final=True)

        finish = traveling.to(arrived)

    celebration = State(final=True)
    done_state_quest = Event(quest.to(celebration))  # type: ignore[arg-type]
