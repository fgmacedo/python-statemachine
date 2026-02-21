from pathlib import Path

import pytest

CURRENT_DIR = Path(__file__).parent
TESTCASES_DIR = CURRENT_DIR

# xfail sets — tests that fail identically on both engines
XFAIL_BOTH = {
    # mandatory — invoke-related (still failing)
    "test187",  # delayed <send> cancelled when sending session terminates before delay
    "test229",  # autoforward: parent forwards events to child automatically
    "test236",  # done.invoke.id arrives after all other child-generated events
    "test240",  # datamodel values passed to invoked child via namelist and <param>
    "test554",  # invocation cancelled when evaluation of invoke arguments errors
    # optional — ecmascript/JSON datamodel
    "test201",  # JSON data in <data> parsed in ecmascript datamodel
    "test446",  # JSON data loaded via src attribute parsed as array
    # optional — Basic HTTP Event I/O Processor
    "test509",  # basic HTTP event I/O processor: send with target
    "test510",  # basic HTTP event I/O processor: send without target
    "test518",  # basic HTTP event I/O processor: event field in POST
    "test519",  # basic HTTP event I/O processor: namelist data in POST body
    "test520",  # basic HTTP event I/O processor: <param> data in POST body
    "test522",  # basic HTTP event I/O processor: <content> in POST body
    "test531",  # basic HTTP event I/O processor: POST response populates _event.data
    "test532",  # basic HTTP event I/O processor: error.communication on bad target
    "test534",  # basic HTTP event I/O processor: #_scxml_sessionid target
    # optional — data/content handling
    "test557",  # XML data in <send> content becomes DOM-like object (python datamodel)
    "test558",  # text data in <send> preserves string type (python datamodel)
    "test561",  # XML content in events creates DOM object
    "test567",  # HTTP message parameters populate _event.data
    "test577",  # <send> without target causes error.communication
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
