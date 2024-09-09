"""
Microwave machine
=================

Example that exercises the Compound and Parallel states.

Compound
--------

If there are more than one substates, one of them is usually designated as the initial state of
that compound state.

When a compound state is active, its substates behave as though they were an active state machine:
 Exactly one child state must also be active.  This means that:

When a compound state is entered, it must also enter exactly one of its substates, usually its
initial state.
When an event happens, the substates have priority when it comes to selecting which transition to
follow. If a substate happens to handles an event, the event is consumed, it isn’t passed to the
parent compound state.
When a substate transitions to another substate, both “inside” the compound state, the compound
state does not exit or enter; it remains active.
When a compound state exits, its substate is simultaneously exited too. (Technically, the substate
exits first, then its parent.)
Compound states may be nested, or include parallel states.

The opposite of a compound state is an atomic state, which is a state with no substates.

A compound state is allowed to define transitions to its child states. Normally, when a transition
leads from a state, it causes that state to be exited.  For transitions from a compound state to
one of its descendants, it is possible to define a transition that avoids exiting and entering
the compound state itself, such transitions are called local transitions.


"""
from statemachine import State
from statemachine import StateMachine


class MicroWave(StateMachine):
    class oven(State.Builder, name="Microwave oven", parallel=True):
        class engine(State.Builder):
            off = State("Off", initial=True)

            class on(State.Builder):
                idle = State("Idle", initial=True)
                cooking = State("Cooking")

                idle.to(cooking, cond="closed.is_active")
                cooking.to(idle, cond="open.is_active")
                cooking.to.itself(internal=True, on="increment_timer")

            turn_off = on.to(off)
            turn_on = off.to(on)
            on.to(off, cond="cook_time_is_over")  # eventless transition

        class door(State.Builder):
            closed = State(initial=True)
            open = State()

            door_open = closed.to(open)
            door_close = open.to(closed)

    def __init__(self):
        self.cook_time = 5
        self.door_closed = True
        self.timer = 0
        super().__init__()
