from statemachine import Event
from statemachine import State
from statemachine import StateChart


class DestroyTheRing(StateChart):
    class quest(State.Compound):
        traveling = State(initial=True)
        completed = State(final=True, donedata="get_quest_result")

        finish = traveling.to(completed)

        def get_quest_result(self):
            return {"ring_destroyed": True, "hero": "frodo"}

    epilogue = State(final=True)
    done_state_quest = Event(quest.to(epilogue, on="capture_result"))  # type: ignore[arg-type]

    def capture_result(self, ring_destroyed=None, hero=None, **kwargs):
        self.received = {"ring_destroyed": ring_destroyed, "hero": hero}
