"""
Error handling -- Quest Recovery
=================================

This example demonstrates **error.execution** handling using ``StateChart``.

When ``error_on_execution=True`` (the ``StateChart`` default), runtime errors in
callbacks are caught and dispatched as ``error.execution`` events instead of
propagating as exceptions. This lets you define error-recovery transitions.

- The ``error_`` naming convention auto-registers both ``error_X`` and ``error.X``
  event names.
- Alternatively, use ``Event(transitions, id="error.execution")`` for explicit
  registration.
- Error data (the original exception, event, etc.) is available in handler kwargs.

"""

from statemachine import Event
from statemachine import State
from statemachine import StateChart


class QuestRecoveryMachine(StateChart):
    """A quest where actions can fail and the error handler routes to recovery.

    When ``on_enter_danger_zone`` raises, the ``error.execution`` event fires
    and transitions to the ``recovering`` state instead of crashing.
    """

    safe = State("Safe", initial=True)
    danger_zone = State("Danger Zone")
    recovering = State("Recovering")
    completed = State("Quest Complete", final=True)

    venture = safe.to(danger_zone)
    survive = danger_zone.to(completed)
    recover = recovering.to(safe)

    # Register error.execution handler using Event with explicit id
    error_execution = Event(
        safe.to(recovering) | danger_zone.to(recovering),
        id="error.execution",
    )

    def on_enter_danger_zone(self):
        # This simulates an unexpected error during a quest action
        raise RuntimeError("Ambush! Orcs attack!")

    def on_enter_recovering(self, error=None, **kwargs):
        if error:
            print(f"Error caught: {error}")
        print("Retreating to recover...")


# %%
# Error triggers recovery instead of crashing
# ----------------------------------------------
#
# When entering ``danger_zone`` raises a ``RuntimeError``, the error is caught
# and dispatched as ``error.execution``. The machine transitions to ``recovering``.

sm = QuestRecoveryMachine()
print(f"Start: {sorted(sm.configuration_values)}")
assert "safe" in sm.configuration_values

sm.send("venture")
print(f"After venture: {sorted(sm.configuration_values)}")
assert "recovering" in sm.configuration_values

# %%
# Recover and try again
# -----------------------

sm.send("recover")
print(f"After recovery: {sorted(sm.configuration_values)}")
assert "safe" in sm.configuration_values


# %%
# Comparison with error_on_execution=False (error propagation)
# --------------------------------------------------------------
#
# With ``error_on_execution=False``, the same error
# would propagate as an exception instead of being caught.


class QuestNoCatch(StateChart):
    error_on_execution = False

    safe = State("Safe", initial=True)
    danger_zone = State("Danger Zone")

    venture = safe.to(danger_zone)

    def on_enter_danger_zone(self):
        raise RuntimeError("Ambush! Orcs attack!")


sm2 = QuestNoCatch()
try:
    sm2.send("venture")
except RuntimeError as e:
    print(f"Exception propagated: {e}")
