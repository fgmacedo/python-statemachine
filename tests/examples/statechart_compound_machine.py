"""
Compound states -- Quest through Middle-earth
==============================================

This example demonstrates compound (hierarchical) states using ``StateChart``.
A compound state contains inner child states, allowing you to model nested behavior.

When a compound state is entered, both the parent and its initial child become active.
Transitions within a compound change the active child while the parent stays active.
Exiting a compound removes all descendants.

"""

from statemachine import State
from statemachine import StateChart


class QuestMachine(StateChart):
    """A quest through Middle-earth with compound states.

    The journey has two compound regions: the ``shire`` (with locations to visit)
    and ``rivendell`` (with council activities). A ``wilderness`` state connects them.
    """

    validate_disconnected_states = False

    class shire(State.Compound):
        bag_end = State("Bag End", initial=True)
        green_dragon = State("The Green Dragon")

        visit_pub = bag_end.to(green_dragon)

    class rivendell(State.Compound):
        council = State("Council of Elrond", initial=True)
        forging = State("Reforging Narsil", final=True)

        begin_forging = council.to(forging)

    wilderness = State("Wilderness")
    destination = State("Quest continues", final=True)

    depart_shire = shire.to(wilderness)
    arrive_rivendell = wilderness.to(rivendell)  # type: ignore[arg-type]
    done_state_rivendell = rivendell.to(destination)


# %%
# Starting the quest
# ------------------
#
# When the machine starts, the ``shire`` compound and its initial child ``bag_end``
# are both active.

sm = QuestMachine()
print(f"Active states: {sorted(sm.configuration_values)}")
assert {"shire", "bag_end"} == set(sm.configuration_values)

# %%
# Transitioning within a compound
# --------------------------------
#
# Moving within a compound changes the active child. The parent stays active.

sm.send("visit_pub")
print(f"After visiting pub: {sorted(sm.configuration_values)}")
assert "shire" in sm.configuration_values
assert "green_dragon" in sm.configuration_values
assert "bag_end" not in sm.configuration_values

# %%
# Exiting a compound
# -------------------
#
# Leaving a compound removes the parent and all children.

sm.send("depart_shire")
print(f"In the wilderness: {sorted(sm.configuration_values)}")
assert {"wilderness"} == set(sm.configuration_values)

# %%
# Entering another compound
# --------------------------
#
# Entering ``rivendell`` activates its initial child ``council``.

sm.send("arrive_rivendell")
print(f"At Rivendell: {sorted(sm.configuration_values)}")
assert {"rivendell", "council"} == set(sm.configuration_values)

# %%
# done.state event
# ------------------
#
# When the final child of a compound is reached, a ``done.state.{parent}`` event
# fires automatically, triggering the transition to ``destination``.

sm.send("begin_forging")
print(f"Quest continues: {sorted(sm.configuration_values)}")
assert {"destination"} == set(sm.configuration_values)
