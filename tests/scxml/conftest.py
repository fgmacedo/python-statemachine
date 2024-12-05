from pathlib import Path

import pytest

from statemachine.io.scxml.processor import SCXMLProcessor

CURRENT_DIR = Path(__file__).parent
TESTCASES_DIR = CURRENT_DIR
SUPPORTED_EXTENSIONS = "scxml"


@pytest.fixture()
def processor(testcase_path: Path):
    """
    Construct a StateMachine class from the SCXML file
    """
    processor = SCXMLProcessor()
    processor.parse_scxml_file(testcase_path)
    return processor


def pytest_generate_tests(metafunc):
    if "testcase_path" not in metafunc.fixturenames:
        return

    fail_marks = [pytest.mark.xfail]

    metafunc.parametrize(
        "testcase_path",
        [
            pytest.param(
                testcase_path,
                id=str(testcase_path.relative_to(TESTCASES_DIR)),
                marks=fail_marks if "fail" in testcase_path.name else [],
            )
            for testcase_path in TESTCASES_DIR.glob("**/*.scxml")
            if "sub" not in testcase_path.name
        ],
    )
