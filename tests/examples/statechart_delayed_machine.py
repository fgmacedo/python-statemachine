"""
Supervised task -- Beacons of Gondor
=====================================

This example demonstrates a **self-driven** ``StateChart`` combining
**compound states**, **parallel states**, **internal events**, **delayed
events**, **eventless transitions**, and **event cancellation**.

- **Compound states** model the beacon chain: each beacon is a sub-state
  of a compound, and the ``light_next`` event advances through them.
- **Parallel states** run the beacon lighting and the siege clock
  concurrently inside a single ``StateChart``.
- ``raise_("event")`` queues an event on the **internal** queue, processed
  immediately within the current macrostep.
- ``send("event", delay=N)`` schedules a delayed event on the **external**
  queue, processed only after ``N`` milliseconds.
- **Eventless transitions** fire automatically when their ``In()`` guard
  becomes true, without requiring an explicit event.
- ``cancel_event(send_id)`` removes a pending event before it fires.

The scenario: Minas Tirith is besieged and the Beacons of Gondor must be
lit to summon Rohan's aid.  Two things happen in parallel:

1. **Beacons** -- Each beacon's ``on_enter`` lights the next via
   ``raise_()``, chaining through all seven relay points in a single
   macrostep (microseconds in wall-clock time).
2. **Siege** -- A delayed ``fall`` event ticks down.  If the beacons
   aren't all lit before the timer expires, the city is overrun.

When the last beacon fires and the signal reaches Rohan, an eventless
transition detects ``In('rohan_reached')`` and transitions the whole
parallel state to the happy ending -- cancelling the siege timer.  If the
siege timer fires first, ``In('fallen')`` triggers the sad ending instead.

.. tip::

   Run with ``-v`` to see the engine's macro/micro step debug log::

       uv run python tests/examples/statechart_delayed_machine.py -v

"""

import logging
import sys

from statemachine import State
from statemachine import StateChart

if "-v" in sys.argv or "--verbose" in sys.argv:
    logging.basicConfig(level=logging.DEBUG, format="%(name)s  %(message)s", stream=sys.stdout)


class BeaconsMachine(StateChart):
    """Light the Beacons of Gondor before the siege overwhelms Minas Tirith.

    A parallel state runs two concurrent regions:

    * **beacons** -- a compound state whose sub-states are the seven beacon
      relay points from Minas Tirith to Rohan.  Each beacon's entry action
      fires ``raise_("light_next")`` to chain to the next one.
    * **siege** -- a compound state with a delayed ``fall`` event that
      represents the city being overrun.

    Two eventless transitions on the parallel state detect the outcome:

    * ``In('rohan_reached')`` -- all beacons lit, Rohan is summoned.
    * ``In('fallen')`` -- siege timer expired, the city falls.
    """

    idle = State("Idle", initial=True)

    class quest(State.Parallel):
        class beacons(State.Compound):
            minas_tirith = State("Minas Tirith", initial=True)
            amon_din = State("Amon Din")
            eilenach = State("Eilenach")
            nardol = State("Nardol")
            erelas = State("Erelas")
            min_rimmon = State("Min-Rimmon")
            calenhad = State("Calenhad")
            rohan_reached = State("Signal reaches Rohan", final=True)

            light_next = (
                minas_tirith.to(amon_din)
                | amon_din.to(eilenach)
                | eilenach.to(nardol)
                | nardol.to(erelas)
                | erelas.to(min_rimmon)
                | min_rimmon.to(calenhad)
                | calenhad.to(rohan_reached)
            )

        class siege(State.Compound):
            holding = State("The city holds", initial=True)
            fallen = State("City overrun", final=True)

            fall = holding.to(fallen)

    rohan_rides = State("Rohan rides to aid!", final=True)
    city_falls = State("Minas Tirith has fallen!", final=True)

    # External event to kick off the quest
    start = idle.to(quest)  # type: ignore[arg-type]

    # Eventless transitions -- checked automatically each macrostep
    quest.to(rohan_rides, cond="In('rohan_reached')")
    quest.to(city_falls, cond="In('fallen')")

    siege_timeout_ms: int = 5000

    def on_enter_minas_tirith(self):
        """Gandalf lights the first beacon.  The chain begins."""
        print("  Minas Tirith -- The beacon is lit!")
        self.raise_("light_next")

    def after_light_next(self, target):
        """Each beacon keeper spots the fire and lights their own."""
        if target.final:
            print(f"  {target.name}!")
        else:
            print(f"  {target.name} -- The beacon is lit!")
            self.raise_("light_next")

    def on_enter_holding(self):
        """The siege clock starts ticking."""
        self.send("fall", delay=self.siege_timeout_ms, send_id="siege_timer")

    def on_enter_rohan_rides(self):
        self.cancel_event("siege_timer")
        print("  The beacons are answered! Rohan rides to aid!")

    def on_enter_city_falls(self):
        print("  The beacons were never lit. Minas Tirith has fallen.")


# %%
# Scenario 1: All beacons lit before the siege
# -----------------------------------------------
#
# A single ``send("start")`` triggers the entire workflow:
#
# 1. Entering the ``quest`` parallel state activates both regions.
# 2. In the **beacons** region, ``on_enter_minas_tirith`` fires
#    ``raise_("light_next")``, and ``after_light_next`` chains through
#    all seven beacons via internal events -- completing in microseconds.
# 3. In the **siege** region, ``on_enter_holding`` schedules a delayed
#    ``fall`` event (5 seconds).
# 4. The eventless guard ``In('rohan_reached')`` becomes true and the
#    machine exits the parallel state into ``rohan_rides``.
# 5. ``on_enter_rohan_rides`` cancels the pending siege timer.

print("=== Scenario 1: Beacons lit in time ===")
sm = BeaconsMachine()
sm.send("start")
print(f"  Result: {sorted(sm.configuration_values)}")
assert "rohan_rides" in sm.configuration_values


# %%
# Scenario 2: The beacons are never lit
# ----------------------------------------
#
# Denethor, in his despair, refuses to light the beacon.  The chain never
# starts.  Because the beacon region stays stuck at ``minas_tirith``, the
# processing loop has nothing to do except busy-wait (sleeping 1 ms per
# cycle) for the delayed ``fall`` event.
#
# The siege timeout is set to just 10 ms for this demonstration -- any
# value > 0 would work since the machine is completely idle while waiting.
# When the delayed ``fall`` event fires, ``holding`` transitions to
# ``fallen``, and the eventless guard ``In('fallen')`` routes the machine
# to ``city_falls``.


class FailedBeaconsMachine(BeaconsMachine):
    """Denethor refuses to light the beacons.  The city is lost."""

    siege_timeout_ms: int = 10

    def on_enter_minas_tirith(self):
        print("  Denethor: 'Why do the fools fly? Better to die sooner than late.'")


print()
print("=== Scenario 2: The beacons are never lit ===")
sm2 = FailedBeaconsMachine()
sm2.send("start")
print(f"  Result: {sorted(sm2.configuration_values)}")
assert "city_falls" in sm2.configuration_values
