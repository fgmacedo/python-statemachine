"""
Parallel states -- War of the Ring
===================================

This example demonstrates parallel states using ``StateChart``.
A parallel state activates all child regions simultaneously. Each region
operates independently -- events in one region don't affect others.

The ``done.state`` event fires only when **all** regions reach a final state.

"""

from statemachine import State
from statemachine import StateChart


class WarMachine(StateChart):
    """The War of the Ring with parallel fronts.

    Three independent fronts run simultaneously inside the ``war`` parallel state:
    Frodo's quest to destroy the Ring, Aragorn's path to kingship, and
    Gandalf's defense of the realms.
    """

    validate_disconnected_states = False

    class war(State.Parallel):
        class frodos_quest(State.Compound):
            shire = State("The Shire", initial=True)
            mordor = State("Mordor")
            mount_doom = State("Mount Doom", final=True)

            journey = shire.to(mordor)
            destroy_ring = mordor.to(mount_doom)

        class aragorns_path(State.Compound):
            ranger = State("Ranger", initial=True)
            king = State("King of Gondor", final=True)

            coronation = ranger.to(king)

        class gandalfs_defense(State.Compound):
            rohan = State("Rohan", initial=True)
            gondor = State("Gondor", final=True)

            ride_to_gondor = rohan.to(gondor)

    peace = State("Peace in Middle-earth", final=True)
    done_state_war = war.to(peace)  # type: ignore[arg-type]


# %%
# All regions activate at once
# -----------------------------
#
# Entering the ``war`` parallel state activates the initial child of every region.

sm = WarMachine()
config = set(sm.configuration_values)
print(f"Active states: {sorted(config)}")
expected = {"war", "frodos_quest", "shire", "aragorns_path", "ranger", "gandalfs_defense", "rohan"}
assert expected.issubset(config)

# %%
# Independent transitions
# ------------------------
#
# An event in one region does not affect others.

sm.send("journey")
print(f"Frodo journeys: {sorted(sm.configuration_values)}")
assert "mordor" in sm.configuration_values
assert "ranger" in sm.configuration_values  # Aragorn unchanged
assert "rohan" in sm.configuration_values  # Gandalf unchanged

# %%
# Partial completion
# -------------------
#
# One region reaching final doesn't end the parallel state.

sm.send("coronation")
print(f"Aragorn crowned: {sorted(sm.configuration_values)}")
assert "king" in sm.configuration_values
assert "war" in sm.configuration_values  # parallel still active

# %%
# All regions reach final
# ------------------------
#
# When all regions reach final, ``done.state.war`` fires and transitions to ``peace``.

sm.send("ride_to_gondor")
print(f"Gandalf in Gondor: {sorted(sm.configuration_values)}")
assert "war" in sm.configuration_values  # Frodo not done yet

sm.send("destroy_ring")
print(f"Peace: {sorted(sm.configuration_values)}")
assert {"peace"} == set(sm.configuration_values)
