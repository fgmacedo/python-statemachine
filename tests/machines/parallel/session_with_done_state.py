from statemachine import State
from statemachine import StateChart


class SessionWithDoneState(StateChart):
    class session(State.Parallel):
        class ui(State.Compound):
            active = State(initial=True)
            closed = State(final=True)

            close_ui = active.to(closed)

        class backend(State.Compound):
            running = State(initial=True)
            stopped = State(final=True)

            stop_backend = running.to(stopped)

    finished = State(final=True)
    done_state_session = session.to(finished)
