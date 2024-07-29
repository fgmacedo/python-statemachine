import io
import sys
from unittest import mock

import pytest


@pytest.fixture(autouse=True, scope="session")
def add_doctest_context(doctest_namespace):  # noqa: PT004
    from statemachine import State
    from statemachine import StateMachine
    from statemachine.utils import run_async_from_sync

    class ContribAsyncio:
        """
        Using `run_async_from_sync` to be injected in the doctests to better integration with an
        already running loop, as all of our examples are also automated executed as doctests.

        On real life code you should use standard `import asyncio; asyncio.run(main())`.
        """

        def __init__(self):
            self.run = run_async_from_sync

    doctest_namespace["State"] = State
    doctest_namespace["StateMachine"] = StateMachine
    doctest_namespace["asyncio"] = ContribAsyncio()


def pytest_ignore_collect(collection_path, path, config):
    if sys.version_info >= (3, 10):  # noqa: UP036
        return None

    if "django_project" in str(path):
        return True


@pytest.fixture(autouse=True, scope="module")
def mock_dot_write(request):
    def open_effect(
        filename,
        mode="r",
        *args,
        **kwargs,
    ):
        if mode in ("r", "rt", "rb"):
            return open(filename, mode, *args, **kwargs)
        elif filename.startswith("/tmp/"):
            return open(filename, mode, *args, **kwargs)
        elif "b" in mode:
            return io.BytesIO()
        else:
            return io.StringIO()

    with mock.patch("pydot.core.io.open", spec=True) as m:
        m.side_effect = open_effect
        yield m
