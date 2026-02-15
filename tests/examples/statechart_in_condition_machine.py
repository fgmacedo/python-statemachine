"""
In() guard condition -- Fellowship Coordination
=================================================

This example demonstrates the **In()** guard condition using ``StateChart``
with parallel states.

``In('state_id')`` checks whether a given state is currently active. This is
especially useful in parallel regions where one region's transitions depend
on the state of another region.

"""

from statemachine import State
from statemachine import StateChart


class FellowshipMachine(StateChart):
    """Fellowship coordination with parallel regions.

    Two parallel regions track Frodo and Sam independently. The key
    transition -- ``sam_to_mordor`` -- uses ``In('mordor_f')`` to ensure Sam
    only follows Frodo to Mordor after Frodo has already arrived there.
    """

    validate_disconnected_states = False

    class quest(State.Parallel):
        class frodo_path(State.Compound):
            shire_f = State("Frodo in Shire", initial=True)
            rivendell_f = State("Frodo at Rivendell")
            mordor_f = State("Frodo in Mordor", final=True)

            frodo_to_rivendell = shire_f.to(rivendell_f)
            frodo_to_mordor = rivendell_f.to(mordor_f)

        class sam_path(State.Compound):
            shire_s = State("Sam in Shire", initial=True)
            rivendell_s = State("Sam at Rivendell")
            mordor_s = State("Sam in Mordor")
            mount_doom_s = State("Sam at Mount Doom", final=True)

            sam_to_rivendell = shire_s.to(rivendell_s)

            # Sam can only go to Mordor when Frodo is already there
            sam_to_mordor = rivendell_s.to(mordor_s, cond="In('mordor_f')")
            sam_to_mount_doom = mordor_s.to(mount_doom_s)

    victory = State("Victory", final=True)
    done_state_quest = quest.to(victory)


# %%
# Initial state -- both in the Shire
# ------------------------------------

sm = FellowshipMachine()
vals = set(sm.configuration_values)
print(f"Start: {sorted(vals)}")
assert "shire_f" in vals
assert "shire_s" in vals

# %%
# Move both to Rivendell independently
# ---------------------------------------

sm.send("frodo_to_rivendell")
sm.send("sam_to_rivendell")
vals = set(sm.configuration_values)
print(f"Both at Rivendell: {sorted(vals)}")
assert "rivendell_f" in vals
assert "rivendell_s" in vals

# %%
# Sam can't go to Mordor yet -- In('mordor_f') is false
# -------------------------------------------------------
#
# Frodo hasn't reached Mordor, so ``In('mordor_f')`` evaluates to false
# and Sam's transition is blocked.

sm.send("sam_to_mordor")
vals = set(sm.configuration_values)
print(f"Sam blocked: {sorted(vals)}")
assert "rivendell_s" in vals  # Sam still at Rivendell

# %%
# Frodo reaches Mordor -- now Sam can follow
# ---------------------------------------------
#
# After Frodo transitions to ``mordor_f``, the ``In('mordor_f')`` condition
# becomes true. Now sending ``sam_to_mordor`` will succeed.

sm.send("frodo_to_mordor")
vals = set(sm.configuration_values)
print(f"Frodo in Mordor: {sorted(vals)}")
assert "mordor_f" in vals
assert "rivendell_s" in vals  # Sam still waiting

# %%
# Sam follows Frodo -- In() guard passes
# ----------------------------------------

sm.send("sam_to_mordor")
vals = set(sm.configuration_values)
print(f"Sam follows: {sorted(vals)}")
assert "mordor_s" in vals

# %%
# Both regions complete -- done.state fires
# -------------------------------------------
#
# When both parallel regions reach their final states, ``done.state.quest``
# fires automatically and transitions to ``victory``.

sm.send("sam_to_mount_doom")
print(f"Victory: {sorted(sm.configuration_values)}")
assert "victory" in sm.configuration_values
