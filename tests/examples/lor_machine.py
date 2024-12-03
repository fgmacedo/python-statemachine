"""
Lord of the Rings Quest - Boolean algebra
=========================================

Example that demonstrates the use of Boolean algebra in conditions.

"""

from statemachine import State
from statemachine import StateMachine
from statemachine.exceptions import TransitionNotAllowed


class LordOfTheRingsQuestStateMachine(StateMachine):
    # Define the states
    shire = State("In the Shire", initial=True)
    bree = State("In Bree")
    rivendell = State("At Rivendell")
    moria = State("In Moria")
    lothlorien = State("In Lothlorien")
    mordor = State("In Mordor")
    mount_doom = State("At Mount Doom", final=True)

    # Define transitions with Boolean conditions
    start_journey = shire.to(bree, cond="frodo_has_ring and !sauron_alive and frodo_stamina > 90")
    meet_elves = bree.to(rivendell, cond="gandalf_present and frodo_has_ring")
    enter_moria = rivendell.to(moria, cond="orc_army_nearby or frodo_has_ring")
    reach_lothlorien = moria.to(lothlorien, cond="!orc_army_nearby")
    journey_to_mordor = lothlorien.to(mordor, cond="frodo_has_ring and sam_is_loyal")
    destroy_ring = mordor.to(mount_doom, cond="frodo_has_ring and frodo_resists_ring")

    # Conditions (attributes representing the state of conditions)
    frodo_stamina: int = 100
    frodo_has_ring: bool = True
    sauron_alive: bool = True  # Initially, Sauron is alive
    gandalf_present: bool = False  # Gandalf is not present at the start
    orc_army_nearby: bool = False
    sam_is_loyal: bool = True
    frodo_resists_ring: bool = False  # Initially, Frodo is not resisting the ring


# %%
# Playing

quest = LordOfTheRingsQuestStateMachine()

# Track state changes
print(f"Current State: {quest.current_state.id}")  # Should start at "shire"

# Step 1: Start the journey
quest.sauron_alive = False  # Assume Sauron is no longer alive
try:
    quest.start_journey()
    print(f"Current State: {quest.current_state.id}")  # Should be "bree"
except TransitionNotAllowed:
    print("Unable to start journey: conditions not met.")

# Step 2: Meet the elves in Rivendell
quest.gandalf_present = True  # Gandalf is now present
try:
    quest.meet_elves()
    print(f"Current State: {quest.current_state.id}")  # Should be "rivendell"
except TransitionNotAllowed:
    print("Unable to meet elves: conditions not met.")

# Step 3: Enter Moria
quest.orc_army_nearby = True  # Orc army is nearby
try:
    quest.enter_moria()
    print(f"Current State: {quest.current_state.id}")  # Should be "moria"
except TransitionNotAllowed:
    print("Unable to enter Moria: conditions not met.")

# Step 4: Reach Lothlorien
quest.orc_army_nearby = False  # Orcs are no longer nearby
try:
    quest.reach_lothlorien()
    print(f"Current State: {quest.current_state.id}")  # Should be "lothlorien"
except TransitionNotAllowed:
    print("Unable to reach Lothlorien: conditions not met.")

# Step 5: Journey to Mordor
try:
    quest.journey_to_mordor()
    print(f"Current State: {quest.current_state.id}")  # Should be "mordor"
except TransitionNotAllowed:
    print("Unable to journey to Mordor: conditions not met.")

# Step 6: Fight with Smeagol
try:
    quest.destroy_ring()
    print(f"Current State: {quest.current_state.id}")  # Should be "mount_doom"
except TransitionNotAllowed:
    print("Unable to destroy the ring: conditions not met.")


# Step 7: Destroy the ring at Mount Doom
quest.frodo_resists_ring = True  # Frodo is now resisting the ring
try:
    quest.destroy_ring()
    print(f"Current State: {quest.current_state.id}")  # Should be "mount_doom"
except TransitionNotAllowed:
    print("Unable to destroy the ring: conditions not met.")
