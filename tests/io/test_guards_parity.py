"""Native ``cond``/``unless`` parity with the Python guard dialect (``docs/guards.md``).

A loaded statechart must accept the same guard forms a class-defined one does: a name can
be a property, a plain attribute or a **method** (called with dependency injection), plus
boolean expressions, as a single value or a list (all must hold). Supporting less would be
an asymmetry. These run under the secure default (``trusted=False``).
"""

import pytest
from statemachine.io import load


def _router(cond=None, unless=None):
    guard = f"cond: {cond}" if cond is not None else f"unless: {unless}"
    return load(
        f"""
        states:
          a:
            initial: true
            transitions:
              - {{event: go, target: passed, {guard}}}
              - {{event: go, target: blocked}}
          passed: {{final: true}}
          blocked: {{final: true}}
        """,
        format="yaml",
    )


class Gate:
    def __init__(self, ready=True, locked=False):
        self._ready = ready
        self._locked = locked

    @property
    def is_ready(self):
        return self._ready

    def is_locked(self):
        return self._locked

    def needs_clearance(self, level=0, **kwargs):
        return level >= 5


@pytest.mark.parametrize(
    ("model", "expected"),
    [(Gate(ready=True), "passed"), (Gate(ready=False), "blocked")],
)
def test_cond_property_is_read(model, expected):
    sm = _router(cond="is_ready")(model=model)
    sm.send("go")
    assert expected in sm.configuration_values


@pytest.mark.parametrize(
    ("model", "expected"),
    [(Gate(locked=True), "passed"), (Gate(locked=False), "blocked")],
)
def test_cond_method_is_called(model, expected):
    # bare method name is *invoked*, not evaluated as a truthy bound method
    sm = _router(cond="is_locked")(model=model)
    sm.send("go")
    assert expected in sm.configuration_values


@pytest.mark.parametrize(("level", "expected"), [(7, "passed"), (2, "blocked")])
def test_cond_method_receives_dependency_injection(level, expected):
    sm = _router(cond="needs_clearance")(model=Gate())
    sm.send("go", level=level)
    assert expected in sm.configuration_values


def test_cond_expression_mixes_property_and_method():
    sm = _router(cond="is_ready and is_locked")(model=Gate(ready=True, locked=True))
    sm.send("go")
    assert "passed" in sm.configuration_values


def test_unless_method_is_called():
    # unless: blocked only if the (called) method is truthy
    sm = _router(unless="is_locked")(model=Gate(locked=True))
    sm.send("go")
    assert "blocked" in sm.configuration_values


def test_cond_list_requires_all():
    sc = load(
        """
        states:
          a:
            initial: true
            transitions:
              - {event: go, target: passed, cond: ["is_ready", "is_locked"]}
              - {event: go, target: blocked}
          passed: {final: true}
          blocked: {final: true}
        """,
        format="yaml",
    )
    assert "blocked" in _go(sc(model=Gate(ready=True, locked=False)))
    assert "passed" in _go(sc(model=Gate(ready=True, locked=True)))


def test_cond_bare_model_attribute_does_not_crash():
    # Regression: a guard whose name matches a non-callable model attribute used to crash
    # at instantiation in the callback dispatcher.
    class Flagged:
        def __init__(self, flag):
            self.flag = flag

    assert "passed" in _go(_router(cond="flag")(model=Flagged(True)))
    assert "blocked" in _go(_router(cond="flag")(model=Flagged(False)))


def _go(sm):
    sm.send("go")
    return sm.configuration_values


@pytest.mark.parametrize(("locked", "expected"), [(True, "passed"), (False, "blocked")])
async def test_cond_sync_method_on_both_engines(sm_runner, locked, expected):
    sm = await sm_runner.start(_router(cond="is_locked"), model=Gate(locked=locked))
    await sm_runner.send(sm, "go")
    assert expected in sm.configuration_values


class AsyncGate:
    def __init__(self, value):
        self._value = value

    async def allowed(self):
        return self._value


class _AsyncListener:
    async def on_enter_state(self, **kwargs): ...


@pytest.mark.parametrize(("value", "expected"), [(True, "passed"), (False, "blocked")])
async def test_cond_async_method_on_async_engine(value, expected):
    # An async guard method is awaited by the async engine (the awaitable-coercion path).
    sm = _router(cond="allowed")(model=AsyncGate(value), listeners=[_AsyncListener()])
    await sm.send("go")
    assert expected in sm.configuration_values
