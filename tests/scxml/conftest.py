from pathlib import Path

import pytest

CURRENT_DIR = Path(__file__).parent
TESTCASES_DIR = CURRENT_DIR


@pytest.fixture(scope="session")
def update_fail_mark(request):
    return request.config.getoption("--upd-fail")


@pytest.fixture(scope="session")
def should_generate_debug_diagram(request):
    return request.config.getoption("--gen-diagram")


@pytest.fixture()
def processor(testcase_path: Path):
    """
    Construct a StateMachine class from the SCXML file
    """
    return processor


def compute_testcase_marks(testcase_path: Path) -> list[pytest.MarkDecorator]:
    marks = [pytest.mark.scxml]
    if testcase_path.with_name(f"{testcase_path.stem}.fail.md").exists():
        marks.append(pytest.mark.xfail)
    if testcase_path.with_name(f"{testcase_path.stem}.skip.md").exists():
        marks.append(pytest.mark.skip)
    return marks


def pytest_generate_tests(metafunc):
    if "testcase_path" not in metafunc.fixturenames:
        return

    metafunc.parametrize(
        "testcase_path",
        [
            pytest.param(
                testcase_path,
                id=str(testcase_path.relative_to(TESTCASES_DIR)),
                marks=compute_testcase_marks(testcase_path),
            )
            for testcase_path in sorted(TESTCASES_DIR.glob("**/*.scxml"))
            if "sub" not in testcase_path.name
        ],
    )
