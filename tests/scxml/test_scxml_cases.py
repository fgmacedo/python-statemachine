from pathlib import Path

import pytest
from statemachine.io.scxml.processor import SCXMLProcessor

from statemachine import StateChart

"""
Test cases as defined by W3C SCXML Test Suite

- https://www.w3.org/Voice/2013/scxml-irp/
- https://alexzhornyak.github.io/SCXML-tutorial/Tests/ecma/W3C/Mandatory/Auto/report__USCXML_2_0_0___msvc2015_32bit__Win7_1.html
- https://github.com/alexzhornyak/PyBlendSCXML/tree/master/w3c_tests
- https://github.com/jbeard4/SCION/wiki/Pseudocode-for-SCION-step-algorithm

"""  # noqa: E501


class AsyncListener:
    """No-op async listener to trigger AsyncEngine selection."""

    async def on_enter_state(
        self, **kwargs
    ): ...  # No-op: presence of async callback triggers AsyncEngine selection


def _run_scxml_testcase(
    testcase_path: Path,
    should_generate_debug_diagram,
    *,
    async_mode: bool = False,
) -> StateChart:
    """Shared logic for sync and async SCXML test variants.

    Parses the SCXML file, starts the state machine, and asserts the final
    configuration contains ``pass``.  Returns the SM instance.
    """
    from statemachine.contrib.diagram import DotGraphMachine

    listeners: list = []
    if async_mode:
        listeners.append(AsyncListener())
    processor = SCXMLProcessor()
    processor.parse_scxml_file(testcase_path)

    sm = processor.start(listeners=listeners)
    if should_generate_debug_diagram:
        DotGraphMachine(sm).get_graph().write_png(
            testcase_path.parent / f"{testcase_path.stem}.png"
        )
    assert isinstance(sm, StateChart)
    return sm


def _assert_passed(sm: StateChart):
    assert isinstance(sm, StateChart)
    assert "pass" in {s.id for s in sm.configuration}


def test_scxml_usecase_sync(testcase_path: Path, should_generate_debug_diagram, caplog):
    sm = _run_scxml_testcase(
        testcase_path,
        should_generate_debug_diagram,
        async_mode=False,
    )
    _assert_passed(sm)


@pytest.mark.asyncio()
async def test_scxml_usecase_async(testcase_path: Path, should_generate_debug_diagram, caplog):
    sm = _run_scxml_testcase(
        testcase_path,
        should_generate_debug_diagram,
        async_mode=True,
    )
    # In async context, the engine only queued __initial__ during __init__.
    # Activate now within the running event loop.
    await sm.activate_initial_state()
    _assert_passed(sm)
