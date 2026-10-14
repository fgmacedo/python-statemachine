"""Run every case generated from the OMG PSSM 1.0 test suite, on both engines.

Each case is a native YAML document loaded untrusted through ``statemachine.io.load``. The
harness listener provides the callbacks the document references and records the trace tokens
they emit; the joined trace must equal one of the case's ``expected_traces``.
"""

import asyncio
import json
import re
import threading
import time
from inspect import isawaitable
from pathlib import Path

import pytest
import yaml
from statemachine.io import load

from .conftest import CASES_DIR
from .conftest import LOWERED
from .conftest import XFAIL_ASYNC
from .conftest import XFAIL_SYNC

SETTLE_TIMEOUT_S = 5.0
MAX_TRACE_TOKENS = 500
"""A longer trace means the machine is looping; the callback raises to stop it."""


def render(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class TraceRecorder:
    """Listener implementing the callbacks named in a case's ``behaviors``.

    A string item appends a trace token, formatted with the event kwargs. Two items appear only
    in a doActivity: ``{send: {event: name}}`` sends that event to the machine, and
    ``{accept: signals}`` parks the doActivity until its state is left, since waiting for an
    event inside a doActivity has no native spelling.
    """

    def __init__(self, behaviors: dict, is_async: bool):
        self.trace: list[str] = []
        self.errors: list[BaseException] = []
        self.parked: set[int] = set()
        self.stop = threading.Event()
        for name, items in behaviors.items():
            if name.startswith("on_invoke_") and is_async:
                setattr(self, name, self._async_callback(items))
            else:
                setattr(self, name, self._callback(items))
        if is_async:
            self.on_enter_state = self._async_noop

    async def _async_noop(self, **kwargs): ...

    def _emit(self, item, machine, kwargs):
        if isinstance(item, str):
            if len(self.trace) >= MAX_TRACE_TOKENS:
                raise RuntimeError("runaway trace: the machine does not settle")
            self.trace.append(item.format(**{k: render(v) for k, v in kwargs.items()}))
            return None
        return machine.send(item["send"]["event"])

    def _callback(self, items):
        def callback(*args, machine=None, ctx=None, **kwargs):
            try:
                for item in items:
                    if "accept" in item:
                        self._park(ctx)
                        return
                    self._emit(item, machine, kwargs)
            except Exception as err:
                self.errors.append(err)
                raise

        return callback

    def _async_callback(self, items):
        async def callback(*args, machine=None, ctx=None, **kwargs):
            try:
                for item in items:
                    if "accept" in item:
                        await self._park_async(ctx)
                        return
                    result = self._emit(item, machine, kwargs)
                    if isawaitable(result):
                        await result
            except Exception as err:
                self.errors.append(err)
                raise

        return callback

    def _park(self, ctx):
        self.parked.add(id(ctx))
        while not ctx.cancelled.wait(0.005) and not self.stop.is_set():
            pass

    async def _park_async(self, ctx):
        self.parked.add(id(ctx))
        while not ctx.cancelled.is_set() and not self.stop.is_set():
            await asyncio.sleep(0.005)


def _invocations_busy(sm, recorder: TraceRecorder) -> bool:
    # The library exposes no public view of running invocations.
    manager = sm._engine._invoke_manager
    running = [
        i
        for i in manager._active.values()
        if not i.terminated and id(i.ctx) not in recorder.parked
    ]
    return bool(manager._pending) or bool(running)


def settle_sync(sm, recorder: TraceRecorder):
    """Wait until every doActivity finished or parked, and its completion was processed."""
    deadline = time.monotonic() + SETTLE_TIMEOUT_S
    while _invocations_busy(sm, recorder):
        assert time.monotonic() < deadline, "doActivity did not finish"
        time.sleep(0.001)


async def settle_async(sm, recorder: TraceRecorder):
    deadline = time.monotonic() + SETTLE_TIMEOUT_S
    while _invocations_busy(sm, recorder):
        assert time.monotonic() < deadline, "doActivity did not finish"
        await asyncio.sleep(0.001)


def load_case(path: Path) -> dict:
    case: dict = yaml.load(path.read_text(), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    return case


def build_machine(case: dict, recorder: TraceRecorder):
    """Load the case untrusted; any error in it fails the case instead of becoming a trace.

    PSSM has no error events. Errors raised inside a step propagate because
    ``catch_errors_as_events`` is off. The wrapped ``send`` records them too, because the
    library drops an error raised while processing a doActivity's completion when that same
    step leaves the doActivity's state, and it records ``error.execution`` sends.
    """
    cls = load(json.dumps(case["statechart"]), format="json", trusted=False, validate=True)
    cls.catch_errors_as_events = False
    original_send = cls.send

    def send(self, event, *args, **kwargs):
        if event == "error.execution":
            recorder.errors.append(kwargs.get("error"))
        try:
            result = original_send(self, event, *args, **kwargs)
        except Exception as err:
            recorder.errors.append(err)
            raise
        return _recording(result, recorder) if isawaitable(result) else result

    cls.send = send  # type: ignore[method-assign]
    return cls(listeners=[recorder])


async def _recording(result, recorder: TraceRecorder):
    try:
        return await result
    except Exception as err:
        recorder.errors.append(err)
        raise


def assert_trace(case: dict, recorder: TraceRecorder):
    assert not recorder.errors, recorder.errors
    trace = "::".join(recorder.trace)
    assert trace in case["expected_traces"], f"trace {trace!r} not expected"


def _stimulus_args(item: dict) -> "tuple[str, dict]":
    name = item["call"] if "call" in item else item["event"]
    return name, item.get("kwargs") or {}


def append_tester_trace(item: dict, recorder: TraceRecorder) -> bool:
    """A ``trace`` stimulus item is a token the tester itself appends."""
    if "trace" in item:
        recorder.trace.append(item["trace"])
        return True
    return False


def trace_result(item: dict, result, recorder: TraceRecorder) -> None:
    """The tester traces the value a call returned."""
    if "trace_result" in item:
        recorder.trace.append(item["trace_result"].format(result=render(result)))


def run_sync(case: dict, recorder: TraceRecorder):
    sm = build_machine(case, recorder)
    settle_sync(sm, recorder)
    for item in case["stimulus"]:
        if append_tester_trace(item, recorder):
            continue
        name, kwargs = _stimulus_args(item)
        trace_result(item, sm.send(name, **kwargs), recorder)
        settle_sync(sm, recorder)


async def run_async(case: dict, recorder: TraceRecorder):
    sm = build_machine(case, recorder)
    await sm.activate_initial_state()
    await settle_async(sm, recorder)
    for item in case["stimulus"]:
        if append_tester_trace(item, recorder):
            continue
        name, kwargs = _stimulus_args(item)
        trace_result(item, await sm.send(name, **kwargs), recorder)
        await settle_async(sm, recorder)


def check_sync(case: dict, recorder: TraceRecorder):
    try:
        run_sync(case, recorder)
    finally:
        recorder.stop.set()
    assert_trace(case, recorder)


def test_pssm_case_sync(pssm_case: Path):
    case = load_case(pssm_case)
    check_sync(case, TraceRecorder(case["behaviors"], is_async=False))


async def test_pssm_case_async(pssm_case: Path):
    case = load_case(pssm_case)
    recorder = TraceRecorder(case["behaviors"], is_async=True)
    try:
        await run_async(case, recorder)
    finally:
        recorder.stop.set()
    assert_trace(case, recorder)


@pytest.mark.parametrize("xfail", [XFAIL_SYNC, XFAIL_ASYNC], ids=["sync", "async"])
def test_every_case_needing_a_construct_is_classified(xfail):
    cases = {path.stem: load_case(path) for path in CASES_DIR.glob("*/*.yaml")}

    assert set(xfail) | set(LOWERED) <= set(cases)
    assert not set(xfail) & set(LOWERED)
    for reasons, prefix in ((xfail, "requires"), (LOWERED, "lowered")):
        for case_id, reason in reasons.items():
            codes = set(re.findall(rf"{prefix}:(\w+)", reason))
            assert codes == set(cases[case_id]["requires"]), case_id
    assert {cid for cid, case in cases.items() if case["requires"]} <= set(xfail) | set(LOWERED)


ERRING_CASE = {
    "expected_traces": ["S1(do)"],
    "stimulus": [],
    "behaviors": {"on_invoke_S1": ["S1(do)"]},
    "statechart": {
        "name": "erring",
        "states": {
            "S1": {
                "initial": True,
                "transitions": [
                    {"event": "done.invoke.S1", "target": "S2", "cond": "undefined_name == 1"}
                ],
            },
            "S2": {},
        },
    },
}


def test_error_after_a_do_activity_fails_the_sync_case():
    recorder = TraceRecorder(ERRING_CASE["behaviors"], is_async=False)

    # Whichever thread processes the completion, the error surfaces.
    with pytest.raises((NameError, AssertionError), match="undefined_name"):
        check_sync(ERRING_CASE, recorder)


async def test_error_after_a_do_activity_fails_the_async_case():
    recorder = TraceRecorder(ERRING_CASE["behaviors"], is_async=True)

    await run_async(ERRING_CASE, recorder)

    with pytest.raises(AssertionError, match="undefined_name"):
        assert_trace(ERRING_CASE, recorder)


ERRING_EXIT_CASE = {
    "expected_traces": ["S1(do)"],
    "stimulus": [],
    "behaviors": {"on_invoke_S1": ["S1(do)"]},
    "statechart": {
        "name": "erring_exit",
        "states": {
            "S1": {
                "initial": True,
                "transitions": [
                    {
                        "event": "done.invoke.S1",
                        "target": "S2",
                        "on": [{"assign": {"location": "x", "expr": "undefined_name + 1"}}],
                    }
                ],
            },
            "S2": {},
        },
    },
}


async def test_error_leaving_a_do_activity_state_fails_the_async_case():
    recorder = TraceRecorder(ERRING_EXIT_CASE["behaviors"], is_async=True)

    await run_async(ERRING_EXIT_CASE, recorder)

    with pytest.raises(AssertionError, match="undefined_name"):
        assert_trace(ERRING_EXIT_CASE, recorder)


def test_error_leaving_a_do_activity_state_fails_the_sync_case():
    recorder = TraceRecorder(ERRING_EXIT_CASE["behaviors"], is_async=False)

    with pytest.raises((NameError, AssertionError), match="undefined_name"):
        check_sync(ERRING_EXIT_CASE, recorder)
