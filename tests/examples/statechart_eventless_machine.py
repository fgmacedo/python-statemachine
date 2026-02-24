"""
Eventless (automatic) transitions -- The One Ring's Corruption
==============================================================

This example demonstrates **eventless transitions** using ``StateChart``.
An eventless transition has no triggering event -- it fires automatically
when its guard condition becomes true during the macrostep processing loop.

Eventless transitions are evaluated after every macrostep. If the condition
is met, the transition fires without any explicit event. Multiple eventless
transitions can cascade in a single macrostep.

"""

from statemachine import State
from statemachine import StateChart


class RingCorruptionMachine(StateChart):
    """The One Ring gradually corrupts its bearer.

    As ``ring_power`` increases, automatic transitions fire when thresholds
    are crossed. No explicit events drive the state changes -- only the
    guard conditions.

    A ``tick`` internal self-transition is used to re-trigger the processing
    loop after changing ``ring_power`` from the outside.
    """

    # States represent corruption stages
    resisting = State("Resisting", initial=True)
    tempted = State("Tempted")
    corrupted = State("Corrupted")
    lost = State("Lost to the Ring", final=True)

    # Eventless transitions: fire automatically when conditions are met
    resisting.to(tempted, cond="is_tempted")
    tempted.to(corrupted, cond="is_corrupted")
    corrupted.to(lost, cond="is_lost")

    # A no-op event to re-trigger the processing loop
    tick = (
        resisting.to.itself(internal=True)
        | tempted.to.itself(internal=True)
        | corrupted.to.itself(internal=True)
    )

    ring_power: int = 0

    def is_tempted(self):
        return self.ring_power >= 3

    def is_corrupted(self):
        return self.ring_power >= 6

    def is_lost(self):
        return self.ring_power >= 9


# %%
# The bearer starts by resisting
# -------------------------------

sm = RingCorruptionMachine()
print(f"Stage: {sorted(sm.configuration_values)}")
assert "resisting" in sm.configuration_values

# %%
# Increase ring power below threshold -- nothing changes
# -------------------------------------------------------
#
# Setting ``ring_power`` alone doesn't trigger processing. We send a ``tick``
# event to re-enter the processing loop where eventless transitions are checked.

sm.ring_power = 2
sm.send("tick")
print(f"Power 2 -> Stage: {sorted(sm.configuration_values)}")
assert "resisting" in sm.configuration_values

# %%
# Cross the first threshold -- automatic transition to "tempted"
# ---------------------------------------------------------------

sm.ring_power = 4
sm.send("tick")
print(f"Power 4 -> Stage: {sorted(sm.configuration_values)}")
assert "tempted" in sm.configuration_values

# %%
# Cross multiple thresholds at once -- cascade in one macrostep
# --------------------------------------------------------------
#
# When ``ring_power`` jumps past several thresholds, all matching eventless
# transitions fire in sequence within a single macrostep.

sm.ring_power = 10
sm.send("tick")
print(f"Power 10 -> Stage: {sorted(sm.configuration_values)}")
assert "lost" in sm.configuration_values
