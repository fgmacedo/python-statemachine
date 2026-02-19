from pathlib import Path

import pytest

CURRENT_DIR = Path(__file__).parent
TESTCASES_DIR = CURRENT_DIR

# xfail sets — tests that fail identically on both engines
XFAIL_BOTH = {
    # mandatory — invoke-related (still failing)
    "test187",
    "test192",
    "test229",
    "test236",
    "test240",
    "test253",
    "test554",
    # optional
    "test201",
    "test446",
    "test509",
    "test510",
    "test518",
    "test519",
    "test520",
    "test522",
    "test531",
    "test532",
    "test534",
    "test557",
    "test558",
    "test561",
    "test567",
    "test577",
}
XFAIL_SYNC_ONLY: set[str] = set()
XFAIL_ASYNC_ONLY: set[str] = set()

XFAIL_SYNC = XFAIL_BOTH | XFAIL_SYNC_ONLY
XFAIL_ASYNC = XFAIL_BOTH | XFAIL_ASYNC_ONLY


@pytest.fixture(scope="session")
def should_generate_debug_diagram(request):
    return request.config.getoption("--gen-diagram")


def compute_testcase_marks(testcase_path: Path, is_async: bool) -> list[pytest.MarkDecorator]:
    marks: list[pytest.MarkDecorator] = [pytest.mark.scxml]
    test_id = testcase_path.stem
    xfail_set = XFAIL_ASYNC if is_async else XFAIL_SYNC
    if test_id in xfail_set:
        marks.append(pytest.mark.xfail)
    return marks


def pytest_generate_tests(metafunc):
    if "testcase_path" not in metafunc.fixturenames:
        return

    is_async = "async" in metafunc.function.__name__

    metafunc.parametrize(
        "testcase_path",
        [
            pytest.param(
                testcase_path,
                id=str(testcase_path.relative_to(TESTCASES_DIR)),
                marks=compute_testcase_marks(testcase_path, is_async),
            )
            for testcase_path in TESTCASES_DIR.glob("**/*.scxml")
            if "sub" not in testcase_path.name
        ],
    )
