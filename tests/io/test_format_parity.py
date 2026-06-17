"""Cross-format parity: the same statechart, authored in ``.scxml``, ``.yaml`` and
``.json``, reaches the same ``pass`` outcome — proving the native floor is the SCXML
ceiling.

Fixtures live in ``format_parity/`` as triples (one file per format). They all run with
``trusted=False`` (the secure default), so this expressivity needs no arbitrary Python.
Some cases are didactic; others are ported from the W3C SCXML mandatory suite (each file
cites its origin) to ensure feature parity with real conformance scenarios.

``format_parity/native/`` holds richer cases that exercise native-only capabilities (the
``before``/``after`` lifecycle slots) and ``trusted=True`` features (``script`` running
arbitrary Python inside callback slots). SCXML cannot express these, so each case is a
``.yaml``/``.json`` pair instead of a format triple.
"""

from pathlib import Path

import pytest
from statemachine.io import load

from ..scxml._harness import assert_passed
from ..scxml._harness import wait_for_completion

FIXTURES = Path(__file__).parent / "format_parity"
FORMATS = (".scxml", ".yaml", ".json")
ALL_FILES = sorted(p for p in FIXTURES.iterdir() if p.suffix in FORMATS)
CASE_STEMS = sorted({p.stem for p in ALL_FILES})

NATIVE_FIXTURES = FIXTURES / "native"
NATIVE_FORMATS = (".yaml", ".json")
NATIVE_FILES = sorted(p for p in NATIVE_FIXTURES.iterdir() if p.suffix in NATIVE_FORMATS)
NATIVE_STEMS = sorted({p.stem for p in NATIVE_FILES})


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
def test_fixture_reaches_pass(path):
    sm = load(path, trusted=False)()
    wait_for_completion(sm)
    assert_passed(sm)


@pytest.mark.parametrize("stem", CASE_STEMS)
def test_case_available_in_all_formats(stem):
    missing = [ext for ext in FORMATS if not (FIXTURES / f"{stem}{ext}").exists()]
    assert not missing, f"{stem} is missing formats: {missing}"


@pytest.mark.parametrize("path", NATIVE_FILES, ids=lambda p: p.name)
def test_native_fixture_reaches_pass(path):
    # validate=True also checks each fixture against the published JSON Schema.
    sm = load(path, trusted=True, validate=True)()
    wait_for_completion(sm)
    assert_passed(sm)


@pytest.mark.parametrize("stem", NATIVE_STEMS)
def test_native_case_available_in_yaml_and_json(stem):
    missing = [ext for ext in NATIVE_FORMATS if not (NATIVE_FIXTURES / f"{stem}{ext}").exists()]
    assert not missing, f"{stem} is missing native formats: {missing}"
