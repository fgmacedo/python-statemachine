import os
from pathlib import Path

import pytest

from .convert import convert

CASES_DIR = Path(__file__).parent / "cases"


def _xmi_path() -> Path:
    value = os.environ.get("PSSM_XMI", "")
    if value and Path(value).is_file():
        return Path(value)
    if os.environ.get("PSSM_REQUIRED"):
        pytest.fail(f"PSSM_REQUIRED is set but PSSM_XMI={value!r} is not a file")
    pytest.skip("PSSM_XMI does not point to the PSSM test suite XMI; see tests/uml/pssm/README.md")


def _yaml_files(root: Path) -> "dict[str, bytes]":
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.glob("*/*.yaml"))}


def test_committed_cases_equal_the_converter_output(tmp_path):
    convert(_xmi_path(), tmp_path)

    generated = _yaml_files(tmp_path)
    committed = _yaml_files(CASES_DIR)

    assert sorted(generated) == sorted(committed)
    stale = [name for name in generated if generated[name] != committed[name]]
    assert not stale, f"regenerate the cases, these differ: {stale}"
