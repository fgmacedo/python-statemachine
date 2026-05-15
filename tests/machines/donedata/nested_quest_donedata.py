from statemachine import Event
from statemachine import State
from statemachine import StateChart


class NestedQuestDoneData(StateChart):
    class outer(State.Compound):
        class inner(State.Compound):
            start = State(initial=True)
            end = State(final=True, donedata="inner_result")

            go = start.to(end)

            def inner_result(self):
                return {"level": "inner"}

        assert isinstance(inner, State)
        after_inner = State(final=True)
        done_state_inner = Event(inner.to(after_inner))  # type: ignore[arg-type]

    final = State(final=True)
    done_state_outer = Event(outer.to(final))  # type: ignore[arg-type]
