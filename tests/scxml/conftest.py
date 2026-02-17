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


def compute_testcase_marks(
    testcase_path: Path,
    variant: str,
) -> list[pytest.MarkDecorator]:
    marks = [pytest.mark.scxml]

    # Only variant-specific marks are recognized (e.g., test191.sync.fail.md).
    # No generic fallback — each variant is tracked independently.
    stem = testcase_path.stem
    parent = testcase_path.parent

    if (parent / f"{stem}.{variant}.fail.md").exists():
        marks.append(pytest.mark.xfail)
    if (parent / f"{stem}.{variant}.skip.md").exists():
        marks.append(pytest.mark.skip)
    return marks


def pytest_generate_tests(metafunc):
    if "testcase_path" not in metafunc.fixturenames:
        return

    # Determine variant from the test function name
    func_name = metafunc.function.__name__
    if func_name.endswith("_async"):
        variant = "async"
    elif func_name.endswith("_sync"):
        variant = "sync"
    else:
        raise ValueError(f"Cannot determine variant from test function name: {func_name}")

    metafunc.parametrize(
        "testcase_path",
        [
            pytest.param(
                testcase_path,
                id=str(testcase_path.relative_to(TESTCASES_DIR)),
                marks=compute_testcase_marks(testcase_path, variant),
            )
            for testcase_path in TESTCASES_DIR.glob("**/*.scxml")
            if "sub" not in testcase_path.name
        ],
    )
