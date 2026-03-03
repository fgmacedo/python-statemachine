from statemachine import Event
from statemachine import State
from statemachine import StateChart


class DestroyTheRingSimple(StateChart):
    class quest(State.Compound):
        traveling = State(initial=True)
        completed = State(final=True, donedata="get_result")

        finish = traveling.to(completed)

        def get_result(self):
            return {"outcome": "victory"}

    celebration = State(final=True)
    done_state_quest = Event(quest.to(celebration))  # type: ignore[arg-type]
