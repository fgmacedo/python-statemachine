from collections import Counter

import pytest
from statemachine.contrib.weighted import _make_weighted_cond
from statemachine.contrib.weighted import _WeightedGroup
from statemachine.contrib.weighted import to
from statemachine.contrib.weighted import weighted_transitions

from statemachine import State
from statemachine import StateChart
from statemachine import StateMachine


@pytest.fixture()
def WeightedIdleSC():
    from tests.examples.weighted_idle_machine import WeightedIdleMachine

    return WeightedIdleMachine


class TestWeightedTransitionsBasic:
    def test_deterministic_with_seed(self, WeightedIdleSC):
        sm = WeightedIdleSC()
        sm.send("idle")
        first_state = sm.current_state

        sm.send("finish")
        sm.send("idle")
        second_state = sm.current_state

        # With seed=42, results are deterministic
        # Create a fresh instance to verify same seed produces same sequence
        sm2 = WeightedIdleSC()
        sm2.send("idle")
        assert sm2.current_state == first_state
        sm2.send("finish")
        sm2.send("idle")
        assert sm2.current_state == second_state

    def test_statistical_distribution(self, WeightedIdleSC):
        """Over many iterations, the distribution should approximate the weights."""
        sm = WeightedIdleSC()
        counts = Counter()
        iterations = 10000

        for _ in range(iterations):
            sm.send("idle")
            counts[sm.current_state.id] += 1
            sm.send("finish")

        # With 70/20/10 weights, check roughly correct distribution (within 5%)
        assert abs(counts["shift_weight"] / iterations - 0.70) < 0.05
        assert abs(counts["adjust_hair"] / iterations - 0.20) < 0.05
        assert abs(counts["bang_shield"] / iterations - 0.10) < 0.05

    def test_single_weighted_transition(self):
        class SingleWeighted(StateChart):
            s1 = State(initial=True)
            s2 = State()

            go = weighted_transitions(s1, (s2, 100), seed=0)
            back = s2.to(s1)

        sm = SingleWeighted()
        sm.send("go")
        assert sm.current_state == SingleWeighted.s2

    def test_equal_weights(self):
        class EqualWeights(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()

            go = weighted_transitions(s1, (s2, 50), (s3, 50))
            back = s2.to(s1) | s3.to(s1)

        sm = EqualWeights()
        counts = Counter()
        iterations = 5000

        for _ in range(iterations):
            sm.send("go")
            counts[sm.current_state.id] += 1
            sm.send("back")

        # Should be roughly 50/50 within 5%
        assert abs(counts["s2"] / iterations - 0.50) < 0.05
        assert abs(counts["s3"] / iterations - 0.50) < 0.05

    def test_float_weights(self):
        class FloatWeights(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()

            go = weighted_transitions(s1, (s2, 0.7), (s3, 0.3))
            back = s2.to(s1) | s3.to(s1)

        sm = FloatWeights()
        counts = Counter()
        iterations = 5000

        for _ in range(iterations):
            sm.send("go")
            counts[sm.current_state.id] += 1
            sm.send("back")

        assert abs(counts["s2"] / iterations - 0.70) < 0.05
        assert abs(counts["s3"] / iterations - 0.30) < 0.05

    def test_mixed_int_and_float_weights(self):
        class MixedWeights(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()

            go = weighted_transitions(s1, (s2, 10), (s3, 5.5), seed=42)
            back = s2.to(s1) | s3.to(s1)

        sm = MixedWeights()
        sm.send("go")
        assert sm.current_state in (MixedWeights.s2, MixedWeights.s3)


class TestWeightedTransitionsWithGuards:
    def test_with_user_cond_guard(self):
        class GuardedWeighted(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()

            go = weighted_transitions(
                s1,
                to(s2, 50, cond="is_allowed"),
                (s3, 50),
                seed=0,
            )
            back = s2.to(s1) | s3.to(s1)

            def is_allowed(self):
                return self.allow_s2

        sm = GuardedWeighted()
        sm.allow_s2 = True

        # When is_allowed=True, both transitions can fire
        counts = Counter()
        for _ in range(1000):
            sm.send("go")
            counts[sm.current_state.id] += 1
            sm.send("back")

        assert counts["s2"] > 0
        assert counts["s3"] > 0

    def test_with_unless_guard(self):
        class UnlessWeighted(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()

            go = weighted_transitions(
                s1,
                to(s2, 90, unless="is_blocked"),
                (s3, 10),
                seed=0,
            )
            back = s2.to(s1) | s3.to(s1)

            def is_blocked(self):
                return self.blocked

        sm = UnlessWeighted()
        sm.blocked = False

        # When not blocked, s2 can fire
        sm.send("go")
        first_state = sm.current_state
        sm.send("back")

        # When blocked, s2 cond fails even if weight selects it
        sm.blocked = True
        results = Counter()
        for _ in range(100):
            try:
                sm.send("go")
                results[sm.current_state.id] += 1
                sm.send("back")
            except Exception:
                results["failed"] += 1

        # s3 should still work when weight selects it
        assert results["s3"] > 0
        assert first_state is not None

    def test_guard_failure_no_fallback(self):
        """When the selected transition's guard fails, no fallback occurs."""

        class NoFallback(StateMachine):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()

            go = weighted_transitions(
                s1,
                to(s2, 90, cond="allow_s2"),
                (s3, 10),
                seed=1,
            )
            back = s2.to(s1) | s3.to(s1)

            allow_s2 = True

        sm = NoFallback()
        sm.allow_s2 = False

        from statemachine.exceptions import TransitionNotAllowed

        got_failure = False
        for _ in range(50):
            try:
                sm.send("go")
                sm.send("back")
            except TransitionNotAllowed:
                got_failure = True
                break

        assert got_failure, "Expected TransitionNotAllowed when guard blocks selection"


class TestWeightedTransitionsValidation:
    def test_empty_destinations(self):
        s1 = State(initial=True)
        with pytest.raises(ValueError, match="requires at least one"):
            weighted_transitions(s1)

    def test_source_not_a_state(self):
        with pytest.raises(TypeError, match="First argument must be a source State"):
            weighted_transitions("not_a_state", ("target", 10))  # type: ignore[arg-type]

    def test_not_a_tuple(self):
        s1 = State(initial=True)
        with pytest.raises(TypeError, match="must be a .* tuple"):
            weighted_transitions(s1, "not a tuple")  # type: ignore[arg-type]

    def test_wrong_tuple_length(self):
        s1 = State(initial=True)
        with pytest.raises(TypeError, match="must be a .* tuple"):
            weighted_transitions(s1, (1, 2, 3, 4))  # type: ignore[arg-type]

    def test_target_not_a_state(self):
        s1 = State(initial=True)
        with pytest.raises(TypeError, match="first element must be a State"):
            weighted_transitions(s1, ("not_a_state", 10))  # type: ignore[arg-type]

    def test_weight_not_a_number(self):
        s1 = State(initial=True)
        s2 = State()
        with pytest.raises(TypeError, match="weight must be a positive number"):
            weighted_transitions(s1, (s2, "ten"))  # type: ignore[arg-type]

    def test_weight_zero(self):
        s1 = State(initial=True)
        s2 = State()
        with pytest.raises(ValueError, match="weight must be positive"):
            weighted_transitions(s1, (s2, 0))

    def test_weight_negative(self):
        s1 = State(initial=True)
        s2 = State()
        with pytest.raises(ValueError, match="weight must be positive"):
            weighted_transitions(s1, (s2, -5))

    def test_kwargs_not_a_dict(self):
        s1 = State(initial=True)
        s2 = State()
        with pytest.raises(TypeError, match="third element must be a dict"):
            weighted_transitions(s1, (s2, 10, "bad"))  # type: ignore[arg-type]

    def test_kwargs_forwarded_to_transition(self):
        """Verify that kwargs dict is forwarded to source.to()."""

        class WithKwargs(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()

            go = weighted_transitions(
                s1,
                (s2, 50, {"on": "do_something"}),
                (s3, 50),
                seed=42,
            )
            back = s2.to(s1) | s3.to(s1)

            def __init__(self):
                self.log = []
                super().__init__()

            def do_something(self):
                self.log.append("did_it")

        sm = WithKwargs()
        # Run enough iterations that s2 is selected at least once
        for _ in range(50):
            sm.send("go")
            sm.send("back")

        assert "did_it" in sm.log

    def test_to_helper_forwards_kwargs(self):
        """Verify that to() helper passes kwargs to source.to()."""

        class WithTo(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()

            go = weighted_transitions(
                s1,
                to(s2, 50, on="do_something"),
                to(s3, 50),
                seed=42,
            )
            back = s2.to(s1) | s3.to(s1)

            def __init__(self):
                self.log = []
                super().__init__()

            def do_something(self):
                self.log.append("did_it")

        sm = WithTo()
        for _ in range(50):
            sm.send("go")
            sm.send("back")

        assert "did_it" in sm.log

    def test_to_returns_tuple(self):
        """to() returns a plain tuple compatible with weighted_transitions."""
        s2 = State()

        result = to(s2, 70)
        assert isinstance(result, tuple)
        assert result == (s2, 70, {})

        result_with_kwargs = to(s2, 30, cond="is_ready", on="go")
        assert isinstance(result_with_kwargs, tuple)
        assert result_with_kwargs == (s2, 30, {"cond": "is_ready", "on": "go"})


class TestWeightedTransitionsWithCallbacks:
    def test_action_decorators_on_weighted_event(self):
        """Transition callbacks (before/on/after) work with weighted transitions."""

        class WithCallbacks(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()

            go = weighted_transitions(s1, (s2, 50), (s3, 50), seed=42)
            back = s2.to(s1) | s3.to(s1)

            def __init__(self):
                self.log = []
                super().__init__()

            def on_go(self):
                self.log.append("on_go")

            def after_go(self):
                self.log.append("after_go")

        sm = WithCallbacks()
        sm.send("go")
        assert "on_go" in sm.log
        assert "after_go" in sm.log


class TestWeightedTransitionsEngines:
    async def test_sync_and_async_engines(self, sm_runner):
        class WeightedSC(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()

            go = weighted_transitions(s1, (s2, 70), (s3, 30), seed=42)
            back = s2.to(s1) | s3.to(s1)

        sm = await sm_runner.start(WeightedSC)
        await sm_runner.send(sm, "go")
        assert "s2" in sm.configuration_values or "s3" in sm.configuration_values
        await sm_runner.send(sm, "back")
        assert "s1" in sm.configuration_values

    async def test_works_with_state_machine(self, sm_runner):
        class WeightedSM(StateMachine):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()

            go = weighted_transitions(s1, (s2, 70), (s3, 30), seed=42)
            back = s2.to(s1) | s3.to(s1)

        sm = await sm_runner.start(WeightedSM)
        await sm_runner.send(sm, "go")
        assert "s2" in sm.configuration_values or "s3" in sm.configuration_values
        await sm_runner.send(sm, "back")
        assert "s1" in sm.configuration_values


class TestMultipleWeightedGroups:
    def test_independent_groups(self):
        class MultiGroup(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()
            s4 = State()
            s5 = State()

            go_a = weighted_transitions(s1, (s2, 80), (s3, 20), seed=42)
            go_b = weighted_transitions(s1, (s4, 30), (s5, 70), seed=99)
            back = s2.to(s1) | s3.to(s1) | s4.to(s1) | s5.to(s1)

        sm = MultiGroup()

        sm.send("go_a")
        state_a = sm.current_state
        assert state_a in (MultiGroup.s2, MultiGroup.s3)
        sm.send("back")

        sm.send("go_b")
        state_b = sm.current_state
        assert state_b in (MultiGroup.s4, MultiGroup.s5)


class TestWeightedCondRepr:
    def test_cond_name_includes_weight_and_percentage(self):
        group = _WeightedGroup([70, 20, 10])
        cond = _make_weighted_cond(0, group, 70.0, 100.0)
        assert cond.__name__ == "weight=70.0 (70%)"

    def test_cond_name_with_fractional_percentage(self):
        group = _WeightedGroup([1, 2])
        cond = _make_weighted_cond(0, group, 1.0, 3.0)
        assert cond.__name__ == "weight=1.0 (33%)"
