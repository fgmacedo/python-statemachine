from pathlib import Path

import pytest

from statemachine import StateChart

from ._harness import assert_passed
from ._harness import async_wait_for_completion
from ._harness import maybe_write_diagram
from ._harness import start_case
from ._harness import wait_for_completion

"""
Test cases as defined by W3C SCXML Test Suite

- https://www.w3.org/Voice/2013/scxml-irp/
- https://alexzhornyak.github.io/SCXML-tutorial/Tests/ecma/W3C/Mandatory/Auto/report__USCXML_2_0_0___msvc2015_32bit__Win7_1.html
- https://github.com/alexzhornyak/PyBlendSCXML/tree/master/w3c_tests
- https://github.com/jbeard4/SCION/wiki/Pseudocode-for-SCION-step-algorithm

The suite is driven through the format-neutral ``statemachine.io.load`` facade (the SCXML
reader feeding the neutral Interpreter), the same entry point used for JSON/YAML.
"""  # noqa: E501


def _run_scxml_testcase(
    testcase_path: Path,
    should_generate_debug_diagram,
    *,
    async_mode: bool = False,
) -> StateChart:
    """Load the SCXML file via ``io.load`` (trusted) and start the state machine."""
    sm = start_case(testcase_path, async_mode=async_mode, trusted=True)
    if should_generate_debug_diagram:
        maybe_write_diagram(sm, testcase_path)
    assert isinstance(sm, StateChart)
    return sm


def test_scxml_usecase_sync(testcase_path: Path, should_generate_debug_diagram, caplog):
    sm = _run_scxml_testcase(testcase_path, should_generate_debug_diagram, async_mode=False)
    wait_for_completion(sm)
    assert_passed(sm)


@pytest.mark.asyncio()
async def test_scxml_usecase_async(testcase_path: Path, should_generate_debug_diagram, caplog):
    sm = _run_scxml_testcase(testcase_path, should_generate_debug_diagram, async_mode=True)
    # In async context, the engine only queued __initial__ during __init__.
    # Activate now within the running event loop.
    await sm.activate_initial_state()
    await async_wait_for_completion(sm)
    assert_passed(sm)
