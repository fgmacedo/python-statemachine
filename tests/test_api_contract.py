"""Contract tests: observable behavior of public Configuration APIs.

Documents the exact values returned by each public API across all supported
topologies (flat, compound, parallel, complex parallel) and lifecycle phases
(initial state, after transitions, final state).

APIs under test (StateChart):
    sm.current_state_value  -- raw value stored on the model
    sm.configuration_values -- OrderedSet of raw values
    sm.configuration        -- OrderedSet[State]
    sm.current_state        -- State or OrderedSet[State] (deprecated)

API under test (Model):
    model.state             -- raw attribute on the model object
"""

import warnings
from typing import Any

import pytest
from statemachine.orderedset import OrderedSet

from statemachine import State
from statemachine import StateChart

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class Model:
    """Explicit model to verify raw state persistence independently."""

    def __init__(self):
        self.state: Any = None


# ---------------------------------------------------------------------------
# Topologies
# ---------------------------------------------------------------------------


class FlatSC(StateChart):
    s1 = State(initial=True)
    s2 = State()
    s3 = State(final=True)

    go = s1.to(s2)
    finish = s2.to(s3)


class CompoundSC(StateChart):
    class parent(State.Compound):
        child1 = State(initial=True)
        child2 = State()
        move = child1.to(child2)

    done = State(final=True)
    leave = parent.to(done)


class ParallelSC(StateChart):
    class regions(State.Parallel):
        class region_a(State.Compound):
            a1 = State(initial=True)
            a2 = State()
            go_a = a1.to(a2)

        class region_b(State.Compound):
            b1 = State(initial=True)
            b2 = State()
            go_b = b1.to(b2)


class ComplexParallelSC(StateChart):
    class top(State.Parallel):
        class left(State.Compound):
            class nested(State.Compound):
                l1 = State(initial=True)
                l2 = State()
                move_l = l1.to(l2)

            left_done = State(final=True)
            finish_left = nested.to(left_done)

        class right(State.Compound):
            r1 = State(initial=True)
            r2 = State()
            move_r = r1.to(r2)


# ---------------------------------------------------------------------------
# Assertion helper
# ---------------------------------------------------------------------------


def assert_contract(sm, model, expected_ids: set):
    """Assert the full observable API contract.

    When exactly one state is active, the model stores a scalar and
    ``current_state`` returns a single ``State``.  When multiple states
    are active (compound/parallel), the model stores an ``OrderedSet``
    and ``current_state`` returns ``OrderedSet[State]``.
    """
    scalar = len(expected_ids) == 1

    # model.state and current_state_value point to the same object
    assert model.state is sm.current_state_value

    if scalar:
        val = next(iter(expected_ids))
        assert model.state == val
        assert not isinstance(model.state, OrderedSet)
    else:
        assert isinstance(model.state, OrderedSet)
        assert set(model.state) == expected_ids

    # configuration_values -- always OrderedSet of raw values
    assert isinstance(sm.configuration_values, OrderedSet)
    assert set(sm.configuration_values) == expected_ids

    # configuration -- always OrderedSet[State]
    assert len(sm.configuration) == len(expected_ids)
    assert {s.id for s in sm.configuration} == expected_ids

    # current_state (deprecated) -- unwrapped when single
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        cs = sm.current_state
    if scalar:
        assert not isinstance(cs, OrderedSet)
        assert cs.id == next(iter(expected_ids))
    else:
        assert isinstance(cs, OrderedSet)
        assert {s.id for s in cs} == expected_ids


# ---------------------------------------------------------------------------
# Main contract matrix: topology x lifecycle x engine
# ---------------------------------------------------------------------------


SCENARIOS = [
    # -- Flat --
    pytest.param(FlatSC, [], {"s1"}, id="flat-initial"),
    pytest.param(FlatSC, ["go"], {"s2"}, id="flat-after-go"),
    pytest.param(FlatSC, ["go", "finish"], {"s3"}, id="flat-final"),
    # -- Compound --
    pytest.param(CompoundSC, [], {"parent", "child1"}, id="compound-initial"),
    pytest.param(CompoundSC, ["move"], {"parent", "child2"}, id="compound-inner-move"),
    pytest.param(CompoundSC, ["leave"], {"done"}, id="compound-exit"),
    # -- Parallel --
    pytest.param(
        ParallelSC,
        [],
        {"regions", "region_a", "a1", "region_b", "b1"},
        id="parallel-initial",
    ),
    pytest.param(
        ParallelSC,
        ["go_a"],
        {"regions", "region_a", "a2", "region_b", "b1"},
        id="parallel-one-region",
    ),
    pytest.param(
        ParallelSC,
        ["go_a", "go_b"],
        {"regions", "region_a", "a2", "region_b", "b2"},
        id="parallel-both-regions",
    ),
    # -- Complex parallel --
    pytest.param(
        ComplexParallelSC,
        [],
        {"top", "left", "nested", "l1", "right", "r1"},
        id="complex-initial",
    ),
    pytest.param(
        ComplexParallelSC,
        ["move_l"],
        {"top", "left", "nested", "l2", "right", "r1"},
        id="complex-nested-move",
    ),
    pytest.param(
        ComplexParallelSC,
        ["move_r"],
        {"top", "left", "nested", "l1", "right", "r2"},
        id="complex-other-region",
    ),
    pytest.param(
        ComplexParallelSC,
        ["move_l", "move_r"],
        {"top", "left", "nested", "l2", "right", "r2"},
        id="complex-both-regions",
    ),
    pytest.param(
        ComplexParallelSC,
        ["finish_left"],
        {"top", "left", "left_done", "right", "r1"},
        id="complex-exit-nested",
    ),
]


@pytest.mark.parametrize(("sc_class", "events", "expected_ids"), SCENARIOS)
async def test_configuration_contract(sm_runner, sc_class, events, expected_ids):
    model = Model()
    sm = await sm_runner.start(sc_class, model=model)
    for event in events:
        await sm_runner.send(sm, event)
    assert_contract(sm, model, expected_ids)


# ---------------------------------------------------------------------------
# Model setter contract
# ---------------------------------------------------------------------------

SETTER_SCENARIOS = [
    pytest.param(FlatSC, "s2", {"s2"}, id="scalar-on-flat"),
    pytest.param(
        CompoundSC,
        OrderedSet(["parent", "child2"]),
        {"parent", "child2"},
        id="orderedset-on-compound",
    ),
    pytest.param(CompoundSC, "done", {"done"}, id="scalar-collapses-orderedset"),
]


@pytest.mark.parametrize(("sc_class", "new_value", "expected_ids"), SETTER_SCENARIOS)
async def test_setter_contract(sm_runner, sc_class, new_value, expected_ids):
    model = Model()
    sm = await sm_runner.start(sc_class, model=model)
    sm.current_state_value = new_value
    assert_contract(sm, model, expected_ids)


async def test_set_none_clears_configuration(sm_runner):
    model = Model()
    sm = await sm_runner.start(FlatSC, model=model)

    sm.current_state_value = None

    assert model.state is None
    assert sm.current_state_value is None
    assert sm.configuration_values == OrderedSet([None])
    assert sm.configuration == OrderedSet()


# ---------------------------------------------------------------------------
# Uninitialized state (async-only: sync enters initial state in __init__)
# ---------------------------------------------------------------------------

UNINITIALIZED_SCENARIOS = [
    pytest.param(FlatSC, {"s1"}, id="flat"),
    pytest.param(CompoundSC, {"parent", "child1"}, id="compound"),
    pytest.param(
        ParallelSC,
        {"regions", "region_a", "a1", "region_b", "b1"},
        id="parallel",
    ),
]


@pytest.mark.parametrize(("sc_class", "expected_ids"), UNINITIALIZED_SCENARIOS)
async def test_uninitialized_then_activated(sc_class, expected_ids):
    from tests.conftest import _AsyncListener

    model = Model()
    sm = sc_class(model=model, listeners=[_AsyncListener()])

    # Before activation: model.state is None, configuration_values wraps it
    assert model.state is None
    assert sm.current_state_value is None
    assert sm.configuration_values == OrderedSet([None])
    assert sm.configuration == OrderedSet()

    # After activation: full contract holds
    await sm.activate_initial_state()
    assert_contract(sm, model, expected_ids)
