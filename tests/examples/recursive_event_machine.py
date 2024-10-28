"""
Looping state machine
=====================

This example demonstrates that you can call an event as a side-effect of another event.
The event will be put on an internal queue and processed in the same loop after the previous event
in the queue is processed.

"""

from statemachine import State
from statemachine import StateMachine


class MyStateMachine(StateMachine):
    startup = State(initial=True)
    test = State()

    counter = 0
    do_startup = startup.to(test, after="do_test")
    do_test = test.to.itself(after="do_test")

    def on_enter_state(self, target, event):
        self.counter += 1
        print(f"{self.counter:>3}: Entering {target} from {event}")

        if self.counter >= 5:
            raise StopIteration


# %%
# Let's create an instance and test the machine.

sm = MyStateMachine()

try:
    sm.do_startup()
except StopIteration:
    pass
