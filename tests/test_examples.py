from pathlib import Path

import pytest

from .helpers import import_module_by_path


def pytest_generate_tests(metafunc):
    if "example_file_wrapper" not in metafunc.fixturenames:
        return

    file_names = [
        pytest.param(example_path, id=f"{example_path}")
        for example_path in Path("tests/examples").glob("**/*_machine.py")
    ]
    metafunc.parametrize("file_name", file_names)


@pytest.fixture()
def example_file_wrapper(file_name):
    def execute_file_wrapper():
        import_module_by_path(file_name)

    return execute_file_wrapper


def test_example(example_file_wrapper):
    """Import the example file so the module is executed"""
    example_file_wrapper()
