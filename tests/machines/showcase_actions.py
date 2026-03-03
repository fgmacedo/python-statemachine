from statemachine import State
from statemachine import StateChart


class ActionsSC(StateChart):
    off = State(initial=True)
    on = State()
    done = State(final=True)

    power_on = off.to(on)
    shutdown = on.to(done)

    def on_exit_off(self): ...
    def on_enter_on(self): ...
    def on_exit_on(self): ...
    def on_enter_done(self): ...
