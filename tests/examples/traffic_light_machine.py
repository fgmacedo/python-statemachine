"""

-------------------
Reusing transitions
-------------------

This example helps to turn visual the different compositions of how to declare
and bind :ref:`transitions` to :ref:`event`.

.. note::

    Even sharing the same transition instance, only the transition actions associated with the
    event will be called.


TrafficLightMachine
   The same transitions are bound to more than one event.

TrafficLightIsolatedTransitions
    We define new transitions, thus, isolating the connection
    between states.

"""

from statemachine import State
from statemachine import StateMachine


class TrafficLightMachine(StateMachine):
    "A traffic light machine"

    green = State(initial=True)
    yellow = State()
    red = State()

    slowdown = green.to(yellow)
    stop = yellow.to(red)
    go = red.to(green)

    cycle = slowdown | stop | go

    def before_slowdown(self):
        print("Slowdown")

    def before_cycle(self, event: str, source: State, target: State, message: str = ""):
        message = ". " + message if message else ""
        return f"Running {event} from {source.id} to {target.id}{message}"

    def on_enter_red(self):
        print("Don't move.")

    def on_exit_red(self):
        print("Go ahead!")


# %%
# Run a transition

sm = TrafficLightMachine()
sm.send("cycle")


# %%


class TrafficLightIsolatedTransitions(StateMachine):
    "A traffic light machine"

    green = State(initial=True)
    yellow = State()
    red = State()

    slowdown = green.to(yellow)
    stop = yellow.to(red)
    go = red.to(green)

    cycle = green.to(yellow) | yellow.to(red) | red.to(green)

    def before_slowdown(self):
        print("Slowdown")

    def before_cycle(self, event: str, source: State, target: State, message: str = ""):
        message = ". " + message if message else ""
        return f"Running {event} from {source.id} to {target.id}{message}"

    def on_enter_red(self):
        print("Don't move.")

    def on_exit_red(self):
        print("Go ahead!")


# %%
# Run a transition

sm2 = TrafficLightIsolatedTransitions()
sm2.send("cycle")
