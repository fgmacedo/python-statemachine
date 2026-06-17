"""Reusable helpers for running conformance/parity cases through the io facade.

Shared by the W3C SCXML suite and the cross-format parity suite so the same case can be
driven from ``.scxml``, ``.yaml`` or ``.json`` and asserted to reach the ``pass`` state.
"""

import asyncio
import time
from pathlib import Path

from statemachine.io import load

from statemachine import StateChart


class AsyncListener:
    """No-op async listener to trigger AsyncEngine selection."""

    async def on_enter_state(self, **kwargs): ...


def start_case(source, *, async_mode: bool = False, trusted: bool = True, **load_kwargs):
    """Load a case (file path or inline content) via ``io.load`` and instantiate it.

    Uses the format-neutral facade, so the same harness works for every format.
    """
    listeners: list = [AsyncListener()] if async_mode else []
    cls = load(source, trusted=trusted, **load_kwargs)
    sm = cls(listeners=listeners)
    return sm


def assert_passed(sm: StateChart):
    assert isinstance(sm, StateChart)
    assert "pass" in {s.id for s in sm.configuration}


def wait_for_completion(sm: StateChart, timeout_s: float = 5.0):
    """Poll the processing loop until the SM reaches a final state or times out."""
    deadline = time.monotonic() + timeout_s
    while not sm.is_terminated and time.monotonic() < deadline:
        time.sleep(0.02)
        # Trigger processing loop to handle events from invoke threads
        sm._engine.processing_loop()


async def async_wait_for_completion(sm: StateChart, timeout_s: float = 5.0):
    """Async variant of :func:`wait_for_completion`."""
    deadline = time.monotonic() + timeout_s
    while not sm.is_terminated and time.monotonic() < deadline:
        await asyncio.sleep(0.02)
        await sm._engine.processing_loop()


def maybe_write_diagram(sm: StateChart, testcase_path: Path):
    from statemachine.contrib.diagram import DotGraphMachine

    DotGraphMachine(sm).get_graph().write_png(testcase_path.parent / f"{testcase_path.stem}.png")
