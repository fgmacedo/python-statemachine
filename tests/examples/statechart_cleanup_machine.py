"""
Cleanup / finalize pattern
===========================

This example demonstrates how to guarantee cleanup code runs after a transition
**regardless of success or failure** — similar to a ``try/finally`` block.

With ``StateChart`` (where ``catch_errors_as_events=True`` by default), errors in
callbacks are caught at the **block level** — meaning the microstep continues
and ``after_<event>()`` callbacks still run. This makes ``after_<event>()`` a
natural **finalize** hook.

For error-specific handling (logging, recovery), define an ``error.execution``
transition and use :func:`raise_() <statemachine.StateMachine.raise_>` to
auto-recover within the same macrostep.

"""

from statemachine import Event
from statemachine import State
from statemachine import StateChart


class ResourceManager(StateChart):
    """A machine that acquires a resource, processes, and always releases it.

    ``after_start`` acts as the **finalize** callback — it runs after the
    ``start`` transition regardless of whether the job succeeds or fails.

    On failure, ``error.execution`` additionally transitions to ``recovering``
    for error-specific handling before auto-recovering back to ``idle``.
    """

    idle = State("Idle", initial=True)
    working = State("Working")
    recovering = State("Recovering")

    start = idle.to(working)
    done = working.to(idle)
    recover = recovering.to(idle)

    error_execution = Event(
        working.to(recovering),
        id="error.execution",
    )

    def __init__(self, job=None):
        self.job = job or (lambda: None)
        super().__init__()

    def on_enter_working(self):
        print("  [working] resource acquired")
        self.job()
        self.raise_("done")

    # --- Finalize (runs on both success and failure) ---

    def after_start(self):
        print("  [after_start] resource released")

    # --- Error-specific handling ---

    def on_enter_recovering(self, error=None, **kwargs):
        print(f"  [recovering] error caught: {error}")
        self.raise_("recover")

    def on_enter_idle(self):
        print("  [idle] ready")


# %%
# Success path
# -------------
#
# When the job completes without errors, the machine transitions
# ``idle → working → idle``. The ``after_start`` callback releases the resource.


def good_job():
    print("  [working] processing... done!")


sm = ResourceManager(job=good_job)
print(f"State: {sorted(sm.configuration_values)}")

sm.send("start")
print(f"State: {sorted(sm.configuration_values)}")

assert "idle" in sm.configuration_values

# %%
# Failure path
# -------------
#
# When the job raises, the error is caught at the block level and
# ``after_start`` **still runs** — releasing the resource. Then
# ``error.execution`` fires, transitioning to ``recovering`` for
# error-specific handling before auto-recovering to ``idle``.


def bad_job():
    print("  [working] processing... oops!")
    raise RuntimeError("something went wrong")


sm2 = ResourceManager(job=bad_job)

sm2.send("start")
print(f"State: {sorted(sm2.configuration_values)}")

assert "idle" in sm2.configuration_values
