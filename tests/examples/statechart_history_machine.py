"""
History states -- Gollum's dual personality
============================================

This example demonstrates history pseudo-states using ``StateChart``.
A history state records the active child of a compound state when it is
exited. Re-entering via the history state restores the previously active
child instead of starting from the initial child.

Both shallow history (``HistoryState()``) and deep history
(``HistoryState(deep=True)``) are shown.

"""

from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart


class PersonalityMachine(StateChart):
    """Gollum's dual personality with shallow history.

    The ``personality`` compound has two children: ``smeagol`` and ``gollum``.
    When Gollum leaves the ``personality`` state and returns via the history
    pseudo-state, the previously active personality is restored.
    """

    validate_disconnected_states = False

    class personality(State.Compound):
        smeagol = State("Smeagol", initial=True)
        gollum = State("Gollum")
        h = HistoryState()

        dark_side = smeagol.to(gollum)
        light_side = gollum.to(smeagol)

    outside = State("Outside")
    leave = personality.to(outside)
    return_via_history = outside.to(personality.h)


# %%
# Shallow history remembers the last child
# ------------------------------------------

sm = PersonalityMachine()
print(f"Initial: {sorted(sm.configuration_values)}")
assert "smeagol" in sm.configuration_values

# Switch to Gollum, then leave
sm.send("dark_side")
print(f"Gollum active: {sorted(sm.configuration_values)}")
assert "gollum" in sm.configuration_values

sm.send("leave")
print(f"Left: {sorted(sm.configuration_values)}")
assert {"outside"} == set(sm.configuration_values)

# Return via history -> Gollum is restored
sm.send("return_via_history")
print(f"History restored: {sorted(sm.configuration_values)}")
assert "gollum" in sm.configuration_values
assert "personality" in sm.configuration_values

# %%
# Multiple exit/reentry cycles
# ------------------------------
#
# History updates each time the compound is exited.

sm.send("light_side")
print(f"Switched to Smeagol: {sorted(sm.configuration_values)}")
assert "smeagol" in sm.configuration_values

sm.send("leave")
sm.send("return_via_history")
print(f"Smeagol restored: {sorted(sm.configuration_values)}")
assert "smeagol" in sm.configuration_values


# %%
# Deep history with nested compounds
# ------------------------------------
#
# Deep history remembers the exact leaf state in nested compounds.


class DeepPersonalityMachine(StateChart):
    """A machine with nested compounds and deep history."""

    validate_disconnected_states = False

    class realm(State.Compound):
        class inner(State.Compound):
            entrance = State("Entrance", initial=True)
            chamber = State("Chamber")

            explore = entrance.to(chamber)

        assert isinstance(inner, State)
        h = HistoryState(deep=True)  # type: ignore[has-type]
        bridge = State("Bridge", final=True)
        flee = inner.to(bridge)

    outside = State("Outside")
    escape = realm.to(outside)
    return_deep = outside.to(realm.h)  # type: ignore[has-type]


sm2 = DeepPersonalityMachine()
print(f"\nDeep history initial: {sorted(sm2.configuration_values)}")
assert "entrance" in sm2.configuration_values

# Move to the inner leaf state
sm2.send("explore")
print(f"Explored chamber: {sorted(sm2.configuration_values)}")
assert "chamber" in sm2.configuration_values

# Exit and return via deep history
sm2.send("escape")
print(f"Escaped: {sorted(sm2.configuration_values)}")
assert {"outside"} == set(sm2.configuration_values)

sm2.send("return_deep")
print(f"Deep history restored: {sorted(sm2.configuration_values)}")
assert "chamber" in sm2.configuration_values
assert "inner" in sm2.configuration_values
assert "realm" in sm2.configuration_values
