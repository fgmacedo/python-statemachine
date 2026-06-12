"""Tests for the Configuration class internals.

These tests cover branches in statemachine/configuration.py that are not
exercised by the higher-level state machine tests.
"""

import warnings

from statemachine.orderedset import OrderedSet

from statemachine import State
from statemachine import StateChart


class ParallelSM(StateChart):
    """A parallel state chart for testing multi-element configuration."""

    s1 = State(initial=True)
    s2 = State()
    s3 = State(final=True)

    go = s1.to(s2)
    finish = s2.to(s3)


class TestConfigurationStatesSetter:
    def test_set_empty_configuration(self):
        sm = ParallelSM()
        assert len(sm.configuration) > 0

        sm.configuration = OrderedSet()
        assert sm.current_state_value is None

    def test_set_multi_element_configuration(self):
        sm = ParallelSM()
        s1_inst = sm.s1
        s2_inst = sm.s2

        sm.configuration = OrderedSet([s1_inst, s2_inst])
        assert isinstance(sm.current_state_value, OrderedSet)
        assert sm.current_state_value == OrderedSet([ParallelSM.s1.value, ParallelSM.s2.value])


class TestConfigurationValueSetter:
    def test_set_value_none_writes_none_to_model(self):
        sm = ParallelSM()
        assert sm.current_state_value is not None

        sm.current_state_value = None
        assert sm.current_state_value is None
        assert sm.configuration_values == OrderedSet()

    def test_set_value_plain_set_coerces_to_ordered_set(self):
        sm = ParallelSM()
        s1_val = ParallelSM.s1.value
        s2_val = ParallelSM.s2.value

        # Assign a plain set (MutableSet but not OrderedSet)
        sm.current_state_value = {s1_val, s2_val}
        # Model should store an OrderedSet (denormalized back to it)
        assert isinstance(sm.current_state_value, OrderedSet)
        assert sm.current_state_value == OrderedSet([s1_val, s2_val])


class TestReadFromModelNonOrderedSet:
    def test_read_from_model_coerces_plain_set(self):
        """When the model stores a plain set, _read_from_model coerces it."""
        sm = ParallelSM()
        s1_val = ParallelSM.s1.value
        s2_val = ParallelSM.s2.value

        # Bypass the value setter to place a plain set on the model
        setattr(sm._config._model, sm._config._state_field, {s1_val, s2_val})

        values = sm._config._read_from_model()
        assert isinstance(values, OrderedSet)
        assert values == OrderedSet([s1_val, s2_val])


class TestConfigurationDiscard:
    def test_discard_nonmatching_scalar(self):
        sm = ParallelSM()
        # current value is s1 (scalar)
        assert sm.current_state_value == ParallelSM.s1.value

        # discard s2 — should be a no-op since s2 is not active
        sm._config.discard(ParallelSM.s2)
        assert sm.current_state_value == ParallelSM.s1.value


class TestConfigurationCurrentState:
    def test_current_state_with_multiple_active_states(self):
        sm = ParallelSM()
        s1_inst = sm.s1
        s2_inst = sm.s2
        sm.configuration = OrderedSet([s1_inst, s2_inst])

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = sm.current_state
        assert isinstance(result, OrderedSet)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Regression tests: add()/discard() must go through the property setter
# so that models with deserializing properties persist the updated value.
# ---------------------------------------------------------------------------


class SerializingModel:
    """A model that serializes/deserializes state on every access,
    simulating a DB-backed property (e.g., Django model field).
    """

    def __init__(self):
        self._raw: str | None = None

    @property
    def state(self):
        if self._raw is None:
            return None
        parts = self._raw.split(",")
        if len(parts) == 1:
            return parts[0]
        return OrderedSet(parts)

    @state.setter
    def state(self, value):
        if value is None:
            self._raw = None
        elif isinstance(value, OrderedSet):
            self._raw = ",".join(str(v) for v in value)
        else:
            self._raw = str(value)


class WarSC(StateChart):
    """Parallel state chart with two regions for testing."""

    class war(State.Parallel):
        class region_a(State.Compound):
            a1 = State(initial=True)
            a2 = State()
            move_a = a1.to(a2)

        class region_b(State.Compound):
            b1 = State(initial=True)
            b2 = State()
            move_b = b1.to(b2)


class TestAddDiscard:
    """Verify add()/discard() always write back through model setter."""

    def test_add_calls_setter_on_serializing_model(self):
        model = SerializingModel()
        sm = WarSC(model=model)

        # After initial entry, all parallel states should be active
        config_values = sm.configuration_values
        assert len(config_values) == 5  # war, region_a, a1, region_b, b1

    def test_discard_calls_setter_on_serializing_model(self):
        model = SerializingModel()
        sm = WarSC(model=model)

        initial_count = len(sm.configuration_values)
        assert initial_count == 5

        # Trigger a transition in region_a: a1 -> a2
        sm.send("move_a")
        config_values = sm.configuration_values
        # a1 should be replaced by a2; still 5 states
        assert len(config_values) == 5
        assert "a2" in config_values
        assert "a1" not in config_values

    def test_parallel_lifecycle_with_serializing_model(self):
        model = SerializingModel()
        sm = WarSC(model=model)

        # Move both regions
        sm.send("move_a")
        sm.send("move_b")

        config_values = sm.configuration_values
        assert len(config_values) == 5
        assert "a2" in config_values
        assert "b2" in config_values
        assert "a1" not in config_values
        assert "b1" not in config_values

    def test_state_restoration_from_serialized_model(self):
        model = SerializingModel()
        sm = WarSC(model=model)
        sm.send("move_a")

        # Save the raw state
        raw_state = model._raw

        # Create a new model with the same raw state and a new SM
        model2 = SerializingModel()
        model2._raw = raw_state
        sm2 = WarSC(model=model2)

        assert sm2.configuration_values == sm.configuration_values

    async def test_parallel_with_serializing_model_both_engines(self, sm_runner):
        model = SerializingModel()
        sm = await sm_runner.start(WarSC, model=model)

        assert len(sm.configuration_values) == 5

        await sm_runner.send(sm, "move_a")
        assert "a2" in sm.configuration_values
        assert len(sm.configuration_values) == 5


# ---------------------------------------------------------------------------
# Regression tests for issue #624: sibling compound states whose children
# share the same ``id`` (e.g. ``a``, ``b``) but use distinct ``value=``
# identifiers must not collapse in ``_instance_states``.
#
# Before the fix, ``_instance_states`` was keyed by ``state.id`` — so two
# states with id ``"a"`` overwrote each other, and event dispatch raised
# ``TransitionNotAllowed`` because the cached configuration resolved to the
# wrong ``State`` instance.  Phase A re-keyed by ``state.value`` (which is
# globally unique, since it's the canonical identifier used by
# ``states_map``).
# ---------------------------------------------------------------------------


class SiblingCompoundChart(StateChart):
    """Canonical repro from issue #624.

    Two sibling ``State.Compound`` regions, each containing children named
    ``a`` and ``b``.  The ``value=`` strings (e.g. ``"g1__a"``) make each
    state globally unique despite the shared local id.
    """

    allow_event_without_transition = False

    class g1(State.Compound):
        a = State(initial=True, value="g1__a")
        b = State(final=True, value="g1__b")
        to_b = a.to(b, event="g1__b")

    class g2(State.Compound):
        a = State(initial=True, value="g2__a")
        b = State(final=True, value="g2__b")
        to_b = a.to(b, event="g2__b")

    advance = g1.to(g2)


class TestSiblingCompoundIdCollision:
    """Regression: sibling compounds with same-named children (#624)."""

    async def test_dispatch_to_g1_inner_state_both_engines(self, sm_runner):
        sm = await sm_runner.start(SiblingCompoundChart)

        # Initial configuration: g1 compound active, g1__a as initial child.
        assert "g1__a" in sm.configuration_values
        assert "g1" in sm.configuration_values

        # Before the fix, this raised TransitionNotAllowed because the
        # _instance_states key "a" was overwritten by g2's "a".
        await sm_runner.send(sm, "g1__b")

        assert "g1__b" in sm.configuration_values
        assert "g1__a" not in sm.configuration_values

    async def test_dispatch_to_g2_inner_state_both_engines(self, sm_runner):
        sm = await sm_runner.start(SiblingCompoundChart)

        # Move from g1 to g2 first.
        await sm_runner.send(sm, "advance")
        assert "g2__a" in sm.configuration_values
        assert "g2" in sm.configuration_values

        # Same scenario as g1, but in the second sibling compound.
        await sm_runner.send(sm, "g2__b")

        assert "g2__b" in sm.configuration_values
        assert "g2__a" not in sm.configuration_values
        assert "g1__b" not in sm.configuration_values

    def test_instance_states_keyed_by_value_no_collision(self):
        """White-box invariant: ``_instance_states`` must not collapse keys.

        Before the fix for #624, ``_instance_states`` was keyed by ``state.id``
        (the Python attribute name) — so sibling compounds with same-named
        children (both ``a``) collapsed to a single entry, leaving the dict
        with fewer entries than ``states_map``. This test pins the post-fix
        invariant: one entry per registered state, keyed by ``state.value``.

        The dispatch tests above prove the correct ``InstanceState`` is
        wrapped at each key (a wrong wrapping would break dispatch).
        """
        sm = SiblingCompoundChart()

        instance_states = sm._config._instance_states  # type: ignore[attr-defined]

        # No key collapse: one entry per registered state.
        assert len(instance_states) == len(sm.states_map)

        # Keyed by the canonical identifier (state.value), matching states_map.
        assert set(instance_states.keys()) == set(sm.states_map.keys())
