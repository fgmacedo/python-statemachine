"""History state behavior with shallow and deep history.

Tests exercise shallow history (remembers last direct child), deep history
(remembers exact leaf in nested compounds), default transitions on first visit,
multiple exit/reentry cycles, and the history_values dict.

Theme: Gollum's dual personality — remembers which was active.
"""

import pytest

from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart


@pytest.mark.timeout(5)
class TestHistoryStates:
    def test_shallow_history_remembers_last_child(self):
        """Exit compound, re-enter via history -> restores last active child."""

        class GollumPersonality(StateChart):
            validate_disconnected_states = False

            class personality(State.Compound):
                smeagol = State(initial=True)
                gollum = State()
                h = HistoryState()

                dark_side = smeagol.to(gollum)
                light_side = gollum.to(smeagol)

            outside = State()
            leave = personality.to(outside)
            return_via_history = outside.to(personality.h)

        sm = GollumPersonality()
        # Switch to gollum
        sm.send("dark_side")
        assert "gollum" in sm.configuration_values

        # Leave compound
        sm.send("leave")
        assert {"outside"} == set(sm.configuration_values)

        # Return via history -> should restore gollum
        sm.send("return_via_history")
        assert "gollum" in sm.configuration_values
        assert "personality" in sm.configuration_values

    def test_shallow_history_default_on_first_visit(self):
        """No prior visit -> history uses default transition target."""

        class GollumPersonality(StateChart):
            validate_disconnected_states = False

            class personality(State.Compound):
                smeagol = State(initial=True)
                gollum = State()
                h = HistoryState()

                dark_side = smeagol.to(gollum)
                _ = h.to(smeagol)  # default: smeagol

            outside = State(initial=True)
            enter_via_history = outside.to(personality.h)
            leave = personality.to(outside)

        sm = GollumPersonality()
        assert {"outside"} == set(sm.configuration_values)

        # First visit via history -> uses default transition -> smeagol
        sm.send("enter_via_history")
        assert "smeagol" in sm.configuration_values

    def test_deep_history_remembers_full_descendant(self):
        """Deep history restores the exact leaf in a nested compound."""

        class DeepMemoryOfMoria(StateChart):
            validate_disconnected_states = False

            class moria(State.Compound):
                class halls(State.Compound):
                    entrance = State(initial=True)
                    chamber = State()

                    explore = entrance.to(chamber)

                assert isinstance(halls, State)
                h = HistoryState(deep=True)
                bridge = State(final=True)
                flee = halls.to(bridge)

            outside = State()
            escape = moria.to(outside)
            return_deep = outside.to(moria.h)

        sm = DeepMemoryOfMoria()
        # Navigate to chamber (deep within nested compound)
        sm.send("explore")
        assert "chamber" in sm.configuration_values

        # Leave
        sm.send("escape")
        assert {"outside"} == set(sm.configuration_values)

        # Return via deep history -> should restore chamber
        sm.send("return_deep")
        assert "chamber" in sm.configuration_values
        assert "halls" in sm.configuration_values
        assert "moria" in sm.configuration_values

    def test_multiple_exits_and_reentries(self):
        """History updates each time we exit the compound."""

        class GollumPersonality(StateChart):
            validate_disconnected_states = False

            class personality(State.Compound):
                smeagol = State(initial=True)
                gollum = State()
                h = HistoryState()

                dark_side = smeagol.to(gollum)
                light_side = gollum.to(smeagol)

            outside = State()
            leave = personality.to(outside)
            return_via_history = outside.to(personality.h)

        sm = GollumPersonality()
        # First: enter as smeagol (initial), leave
        sm.send("leave")
        sm.send("return_via_history")
        assert "smeagol" in sm.configuration_values

        # Switch to gollum, leave, return
        sm.send("dark_side")
        sm.send("leave")
        sm.send("return_via_history")
        assert "gollum" in sm.configuration_values

        # Switch back to smeagol, leave, return
        sm.send("light_side")
        sm.send("leave")
        sm.send("return_via_history")
        assert "smeagol" in sm.configuration_values

    def test_history_after_state_change(self):
        """Change state within compound, exit, re-enter -> new state restored."""

        class GollumPersonality(StateChart):
            validate_disconnected_states = False

            class personality(State.Compound):
                smeagol = State(initial=True)
                gollum = State()
                h = HistoryState()

                dark_side = smeagol.to(gollum)

            outside = State()
            leave = personality.to(outside)
            return_via_history = outside.to(personality.h)

        sm = GollumPersonality()
        sm.send("dark_side")
        sm.send("leave")
        sm.send("return_via_history")
        assert "gollum" in sm.configuration_values

    def test_shallow_only_remembers_immediate_child(self):
        """Shallow history in nested compound restores direct child, not grandchild."""

        class ShallowMoria(StateChart):
            validate_disconnected_states = False

            class moria(State.Compound):
                class halls(State.Compound):
                    entrance = State(initial=True)
                    chamber = State()

                    explore = entrance.to(chamber)

                assert isinstance(halls, State)
                h = HistoryState(deep=False)
                bridge = State(final=True)
                flee = halls.to(bridge)

            outside = State()
            escape = moria.to(outside)
            return_shallow = outside.to(moria.h)

        sm = ShallowMoria()
        sm.send("explore")
        assert "chamber" in sm.configuration_values

        sm.send("escape")
        sm.send("return_shallow")
        # Shallow history restores 'halls' as the direct child,
        # but re-enters halls at its initial state (entrance), not chamber
        assert "halls" in sm.configuration_values
        assert "entrance" in sm.configuration_values

    def test_history_values_dict_populated(self):
        """sm.history_values[history_id] has saved states after exit."""

        class GollumPersonality(StateChart):
            validate_disconnected_states = False

            class personality(State.Compound):
                smeagol = State(initial=True)
                gollum = State()
                h = HistoryState()

                dark_side = smeagol.to(gollum)

            outside = State()
            leave = personality.to(outside)
            return_via_history = outside.to(personality.h)

        sm = GollumPersonality()
        sm.send("dark_side")
        sm.send("leave")
        assert "h" in sm.history_values
        saved = sm.history_values["h"]
        assert len(saved) == 1
        assert saved[0].id == "gollum"

    def test_history_with_default_transition(self):
        """HistoryState with explicit default .to() transition."""

        class GollumPersonality(StateChart):
            validate_disconnected_states = False

            class personality(State.Compound):
                smeagol = State(initial=True)
                gollum = State()
                h = HistoryState()

                dark_side = smeagol.to(gollum)
                _ = h.to(gollum)  # default: gollum (not the initial smeagol)

            outside = State(initial=True)
            enter_via_history = outside.to(personality.h)
            leave = personality.to(outside)

        sm = GollumPersonality()
        # First visit via history -> uses default transition -> gollum
        sm.send("enter_via_history")
        assert "gollum" in sm.configuration_values
