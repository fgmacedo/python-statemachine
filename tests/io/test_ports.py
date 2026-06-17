"""Tests for the format port (Protocol) and the format registry."""

from pathlib import Path

import pytest

# Importing the loader registers the built-in formats.
import statemachine.io.loader  # noqa: F401
from statemachine.io.ports import FormatReader
from statemachine.io.ports import FormatSpec
from statemachine.io.ports import detect_format
from statemachine.io.ports import get_format
from statemachine.io.ports import register_format


class TestDetectFormat:
    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("m.scxml", "scxml"),
            ("m.xml", "scxml"),
            ("m.json", "json"),
            ("m.yaml", "yaml"),
            ("m.yml", "yaml"),
            ("M.SCXML", "scxml"),
        ],
    )
    def test_detect_by_extension(self, filename, expected):
        assert detect_format(Path(filename)) == expected

    def test_explicit_overrides_extension(self):
        assert detect_format(Path("m.json"), "yaml") == "yaml"

    def test_unknown_extension_raises(self):
        with pytest.raises(ValueError, match="Cannot detect format"):
            detect_format(Path("m.txt"))


class TestGetFormat:
    def test_known(self):
        assert get_format("json").name == "json"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            get_format("toml")


class TestRegistry:
    def test_register_and_lookup(self):
        class _Reader:
            def read(self, text, *, source_name=None):  # pragma: no cover - not called
                ...

        spec = FormatSpec(
            name="dummy",
            extensions=(".dummy",),
            reader_factory=_Reader,
        )
        register_format(spec)
        assert get_format("dummy") is spec
        assert detect_format(Path("x.dummy")) == "dummy"

    def test_readers_satisfy_protocol(self):
        from statemachine.io.json.reader import JSONReader
        from statemachine.io.scxml.reader import SCXMLReader
        from statemachine.io.yaml.reader import YAMLReader

        assert isinstance(JSONReader(), FormatReader)
        assert isinstance(YAMLReader(), FormatReader)
        assert isinstance(SCXMLReader(), FormatReader)
