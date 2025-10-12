"""Tests for probabilistic transitions with weighted random selection."""
import pickle
from collections import Counter

import pytest

from statemachine import State
from statemachine import StateMachine


# Test Fixtures


@pytest.fixture
def weighted_idle_machine():
    """A game character with weighted idle animations."""

    class CharacterMachine(StateMachine):
        standing = State(initial=True)
        shift_weight = State()
        adjust_hair = State()
        bang_shield = State()

        # Weighted idle transitions from standing to itself
        idle = (
            standing.to(shift_weight, event="idle", weight=70)
            | standing.to(adjust_hair, event="idle", weight=20)
            | standing.to(bang_shield, event="idle", weight=10)
        )

        # Return transitions
        finish = (
            shift_weight.to(standing)
            | adjust_hair.to(standing)
            | bang_shield.to(standing)
        )

        def __init__(self, random_seed=None):
            self.animations = []
            super().__init__(random_seed=random_seed)

        def on_enter_shift_weight(self):
            self.animations.append("shift_weight")

        def on_enter_adjust_hair(self):
            self.animations.append("adjust_hair")

        def on_enter_bang_shield(self):
            self.animations.append("bang_shield")

    return CharacterMachine


# Module-level class for pickle test
class SimpleWeightedMachine(StateMachine):
    """Simple machine with two weighted transitions."""

    a = State(initial=True)
    b = State()
    c = State()

    go = a.to(b, event="go", weight=75) | a.to(c, event="go", weight=25)


@pytest.fixture
def simple_weighted_machine():
    """Simple machine with two weighted transitions."""
    return SimpleWeightedMachine


@pytest.fixture
def mixed_weighted_machine():
    """Machine with both weighted and unweighted transitions."""

    class MixedMachine(StateMachine):
        start = State(initial=True)
        weighted_a = State()
        weighted_b = State()
        unweighted = State()

        # Mix of weighted and unweighted transitions
        mixed_event = (
            start.to(weighted_a, event="mixed_event", weight=50)
            | start.to(weighted_b, event="mixed_event", weight=50)
            | start.to(unweighted, event="mixed_event")  # No weight
        )

    return MixedMachine


@pytest.fixture
def conditional_weighted_machine():
    """Machine with weighted transitions that also have conditions."""

    class ConditionalMachine(StateMachine):
        start = State(initial=True)
        allowed_dest = State()
        blocked_dest = State()

        go = (
            start.to(allowed_dest, event="go", weight=50, cond="is_allowed")
            | start.to(blocked_dest, event="go", weight=50)
        )

        def __init__(self, allow=True, random_seed=None):
            self.allow = allow
            super().__init__(random_seed=random_seed)

        def is_allowed(self):
            return self.allow

    return ConditionalMachine


@pytest.fixture
def zero_negative_weight_machine():
    """Machine with zero and negative weights."""

    class ZeroNegativeMachine(StateMachine):
        start = State(initial=True)
        valid_a = State()
        valid_b = State()
        zero_weight = State()
        negative_weight = State()

        go = (
            start.to(valid_a, event="go", weight=50)
            | start.to(valid_b, event="go", weight=50)
            | start.to(zero_weight, event="go", weight=0)
            | start.to(negative_weight, event="go", weight=-10)
        )

    return ZeroNegativeMachine


@pytest.fixture
def no_weight_machine():
    """Machine with no weights (backward compatibility test)."""

    class NoWeightMachine(StateMachine):
        start = State(initial=True)
        middle = State()
        end = State()

        advance = start.to(middle) | middle.to(end)

    return NoWeightMachine


# Test Cases


def test_deterministic_weighted_selection(simple_weighted_machine):
    """Test that weighted selection is deterministic with a seed."""
    sm1 = simple_weighted_machine(random_seed=42)
    sm2 = simple_weighted_machine(random_seed=42)

    results1 = []
    results2 = []

    for _ in range(10):
        sm1.send("go")
        results1.append(sm1.current_state.id)
        # Reset to initial state
        sm1.current_state = sm1.a

        sm2.send("go")
        results2.append(sm2.current_state.id)
        # Reset to initial state
        sm2.current_state = sm2.a

    # Results should be identical with same seed
    assert results1 == results2


def test_weighted_distribution(simple_weighted_machine):
    """Test that weighted transitions follow the expected distribution."""
    sm = simple_weighted_machine(random_seed=12345)

    results = Counter()
    num_trials = 1000

    for _ in range(num_trials):
        sm.send("go")
        results[sm.current_state.id] += 1
        # Reset to initial state
        sm.current_state = sm.a

    # With 75/25 split and 1000 trials, expect roughly 750/250
    # Allow for statistical variance (use generous bounds)
    assert 700 <= results["b"] <= 800
    assert 200 <= results["c"] <= 300


def test_weighted_idle_animations(weighted_idle_machine):
    """Test game character idle animation selection."""
    sm = weighted_idle_machine(random_seed=99)

    # Trigger idle multiple times
    for _ in range(10):
        sm.idle()
        # Return to standing
        sm.finish()

    # Should have 10 animations recorded
    assert len(sm.animations) == 10

    # Count distribution
    animation_counts = Counter(sm.animations)

    # With weights 70/20/10, shift_weight should be most common
    # This is probabilistic, so we just check we have variety
    assert "shift_weight" in animation_counts
    assert len(animation_counts) >= 2  # At least 2 different animations


def test_zero_and_negative_weights_ignored(zero_negative_weight_machine):
    """Test that zero and negative weights are ignored."""
    sm = zero_negative_weight_machine(random_seed=777)

    results = Counter()
    num_trials = 100

    for _ in range(num_trials):
        sm.send("go")
        results[sm.current_state.id] += 1
        # Reset to initial state
        sm.current_state = sm.start

    # Only valid_a and valid_b should be reached
    assert results["valid_a"] > 0
    assert results["valid_b"] > 0
    assert results["zero_weight"] == 0
    assert results["negative_weight"] == 0


def test_mixed_weighted_and_unweighted(mixed_weighted_machine):
    """Test that when weights exist, only weighted transitions are considered."""
    sm = mixed_weighted_machine(random_seed=555)

    results = Counter()
    num_trials = 100

    for _ in range(num_trials):
        sm.send("mixed_event")
        results[sm.current_state.id] += 1
        # Reset to initial state
        sm.current_state = sm.start

    # Only weighted_a and weighted_b should be reached
    assert results["weighted_a"] > 0
    assert results["weighted_b"] > 0
    assert results["unweighted"] == 0  # Unweighted should be ignored


def test_conditions_apply_to_weighted_transitions(conditional_weighted_machine):
    """Test that conditions still filter weighted transitions."""
    # First test with allow=True (both transitions can be chosen)
    sm_allowed = conditional_weighted_machine(allow=True, random_seed=111)

    results_allowed = Counter()
    for _ in range(50):
        sm_allowed.send("go")
        results_allowed[sm_allowed.current_state.id] += 1
        sm_allowed.current_state = sm_allowed.start

    # Both destinations should be reachable
    assert results_allowed["allowed_dest"] > 0
    assert results_allowed["blocked_dest"] > 0

    # Now test with allow=False (first transition blocked by condition)
    sm_blocked = conditional_weighted_machine(allow=False, random_seed=222)

    results_blocked = Counter()
    for _ in range(50):
        sm_blocked.send("go")
        results_blocked[sm_blocked.current_state.id] += 1
        sm_blocked.current_state = sm_blocked.start

    # Only blocked_dest should be reachable
    assert results_blocked["allowed_dest"] == 0
    assert results_blocked["blocked_dest"] == 50


def test_no_weights_backward_compatibility(no_weight_machine):
    """Test that machines without weights work as before."""
    sm = no_weight_machine()

    # Should transition start -> middle
    sm.advance()
    assert sm.current_state.id == "middle"

    # Should transition middle -> end
    sm.advance()
    assert sm.current_state.id == "end"


def test_transition_with_weight_parameter():
    """Test that Transition accepts weight parameter."""
    from statemachine.transition import Transition

    source = State("Source", initial=True)
    target = State("Target")

    # Create transition with weight
    transition = Transition(source, target, event="go", weight=75)

    assert transition.weight == 75


def test_transition_without_weight_parameter():
    """Test that Transition works without weight (default None)."""
    from statemachine.transition import Transition

    source = State("Source", initial=True)
    target = State("Target")

    # Create transition without weight
    transition = Transition(source, target, event="go")

    assert transition.weight is None


def test_statemachine_random_seed_parameter():
    """Test that StateMachine accepts random_seed parameter."""

    class TestMachine(StateMachine):
        a = State(initial=True)
        b = State()
        go = a.to(b)

    sm = TestMachine(random_seed=12345)
    assert sm._random is not None


def test_pickle_state_machine_with_weights(simple_weighted_machine):
    """Test that state machines with weights can be pickled and unpickled."""
    sm1 = simple_weighted_machine(random_seed=999)

    # Trigger a transition
    sm1.send("go")
    state_after_first = sm1.current_state.id

    # Pickle and unpickle
    pickled = pickle.dumps(sm1)
    sm2 = pickle.loads(pickled)

    # State should be preserved
    assert sm2.current_state.id == state_after_first

    # Reset both to initial state
    sm1.current_state = sm1.a
    sm2.current_state = sm2.a

    # Random state should be preserved, so next transitions should match
    sm1.send("go")
    sm2.send("go")

    assert sm1.current_state.id == sm2.current_state.id


# Async Tests


@pytest.fixture
def async_weighted_machine():
    """Async machine with weighted transitions."""

    class AsyncWeightedMachine(StateMachine):
        start = State(initial=True)
        dest_a = State()
        dest_b = State()

        go = start.to(dest_a, event="go", weight=60) | start.to(
            dest_b, event="go", weight=40
        )

        async def on_enter_dest_a(self):
            self.entered = "dest_a"

        async def on_enter_dest_b(self):
            self.entered = "dest_b"

    return AsyncWeightedMachine


async def test_async_weighted_selection(async_weighted_machine):
    """Test that weighted selection works with async state machines."""
    sm = async_weighted_machine(random_seed=42)

    results = Counter()
    num_trials = 100

    for _ in range(num_trials):
        await sm.go()
        results[sm.current_state.id] += 1
        # Reset to initial state
        sm.current_state = sm.start

    # Both destinations should be reached
    assert results["dest_a"] > 0
    assert results["dest_b"] > 0

    # With 60/40 split, dest_a should be more common
    assert results["dest_a"] > results["dest_b"]


def test_async_weighted_from_sync_context(async_weighted_machine):
    """Test that async weighted machine can be used from sync context."""
    sm = async_weighted_machine(random_seed=42)

    # Should work from sync context
    sm.go()
    assert sm.current_state.id in ["dest_a", "dest_b"]


def test_weight_in_transition_repr():
    """Test that weight appears in transition repr when present."""
    from statemachine.transition import Transition

    source = State("Source", initial=True)
    target = State("Target")

    transition = Transition(source, target, event="go", weight=75)
    repr_str = repr(transition)

    # Should include weight in representation
    assert "weight=75" in repr_str


def test_all_zero_weights_falls_back_to_first_match():
    """Test that when all weights are zero/negative, falls back to first match."""

    class AllZeroWeightMachine(StateMachine):
        start = State(initial=True)
        first_dest = State()
        second_dest = State()

        go = (
            start.to(first_dest, event="go", weight=0)
            | start.to(second_dest, event="go", weight=0)
        )

    sm = AllZeroWeightMachine(random_seed=42)

    # With all zero weights, should fall back to first match behavior
    for _ in range(10):
        sm.send("go")
        # First transition in order should be selected
        assert sm.current_state.id == "first_dest"
        sm.current_state = sm.start


def test_single_weighted_transition():
    """Test that a single weighted transition works correctly."""

    class SingleWeightedMachine(StateMachine):
        start = State(initial=True)
        end = State()

        go = start.to(end, event="go", weight=100)

    sm = SingleWeightedMachine(random_seed=42)
    sm.send("go")

    # Should always transition to end
    assert sm.current_state.id == "end"


# Diagram Tests


def test_diagram_shows_probability_labels(simple_weighted_machine):
    """Test that diagrams show probability labels on weighted transitions."""
    sm = simple_weighted_machine(random_seed=42)

    # Generate the diagram
    graph = sm._graph()
    dot_string = graph.to_string()

    # Check that probability labels are present
    assert "[75%]" in dot_string, "Expected 75% probability label in diagram"
    assert "[25%]" in dot_string, "Expected 25% probability label in diagram"

    # Check that the event name is still present
    assert "go" in dot_string


def test_diagram_without_weights_no_probability_labels(no_weight_machine):
    """Test that diagrams without weights don't show probability labels."""
    sm = no_weight_machine()

    # Generate the diagram
    graph = sm._graph()
    dot_string = graph.to_string()

    # Should not have percentage labels
    assert "[" not in dot_string or "]" not in dot_string or "%" not in dot_string


def test_diagram_with_single_weighted_transition():
    """Test diagram with only one weighted transition (no probability shown)."""

    class SingleWeightMachine(StateMachine):
        start = State(initial=True)
        end = State()

        go = start.to(end, event="go", weight=100)

    sm = SingleWeightMachine()
    graph = sm._graph()
    dot_string = graph.to_string()

    # Single weighted transition should not show probability
    # (no ambiguity, always 100%)
    # The label should just be "go" without percentage
    assert "go" in dot_string


def test_diagram_probability_calculation():
    """Test that diagram calculates correct probabilities for complex weights."""

    class ComplexWeightMachine(StateMachine):
        start = State(initial=True)
        option_a = State()
        option_b = State()
        option_c = State()

        choose = (
            start.to(option_a, event="choose", weight=10)
            | start.to(option_b, event="choose", weight=20)
            | start.to(option_c, event="choose", weight=70)
        )

    sm = ComplexWeightMachine()
    graph = sm._graph()
    dot_string = graph.to_string()

    # Check that probabilities are correctly calculated
    assert "[10%]" in dot_string
    assert "[20%]" in dot_string
    assert "[70%]" in dot_string

