from statemachine import State
from statemachine import StateChart


class OrderWorkflow(StateChart):
    pending = State(initial=True)
    processing = State()
    done = State()
    completed = State(final=True)
    cancelled = State(final=True)

    process = pending.to(processing)
    complete = processing.to(done)
    finish = done.to(completed)
    cancel = cancelled.from_.any()


class OrderWorkflowCompound(StateChart):
    class active(State.Compound):
        pending = State(initial=True)
        processing = State()
        done = State(final=True)

        process = pending.to(processing)
        complete = processing.to(done)

    completed = State(final=True)
    cancelled = State(final=True)
    done_state_active = active.to(completed)
    cancel = active.to(cancelled)
