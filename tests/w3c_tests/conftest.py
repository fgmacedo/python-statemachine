from pathlib import Path

import pytest

CURRENT_DIR = Path(__file__).parent
TESTCASES_DIR = CURRENT_DIR / "testcases"
SUPPORTED_EXTENSIONS = "scxml"


@pytest.fixture()
def sm_class(testcase_path: Path):
    """
    Construct a StateMachine class from the SCXML file
    """
    from statemachine.io import create_machine_class_from_definition
    from statemachine.io.scxml import parse_scxml

    # Read SCXML content
    scxml_content = testcase_path.read_text()

    # Parse SCXML into dictionary format
    definition = parse_scxml(scxml_content)

    # Create state machine class
    try:
        return create_machine_class_from_definition("SCXMLStateMachine", definition)
    except Exception as e:
        raise Exception(
            f"Failed to create state machine class: {e} from definition: {definition}"
        ) from e


def pytest_generate_tests(metafunc):
    if "testcase_path" not in metafunc.fixturenames:
        return

    fail_marks = [pytest.mark.xfail]

    metafunc.parametrize(
        "testcase_path",
        [
            pytest.param(
                testcase_path,
                id=str(testcase_path.name),
                marks=fail_marks if "ok" not in testcase_path.name else [],
            )
            for testcase_path in TESTCASES_DIR.glob("**/*.scxml")
        ],
    )
