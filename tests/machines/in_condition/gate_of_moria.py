from statemachine import State
from statemachine import StateChart


class GateOfMoria(StateChart):
    outside = State(initial=True)
    at_gate = State()
    inside = State(final=True)

    approach = outside.to(at_gate)
    # Can only enter if we are at the gate
    enter_gate = outside.to(inside, cond="In('at_gate')")
    speak_friend = at_gate.to(inside)
