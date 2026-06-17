"""Tests for the high-level ``io.load`` / ``io.build_processor`` facade."""

import json

import pytest
from statemachine.exceptions import InvalidDefinition
from statemachine.io import build_processor
from statemachine.io import load
from statemachine.statemachine import StateChart

TOGGLE_NATIVE = {
    "name": "Toggle",
    "states": {
        "on": {"initial": True, "transitions": [{"event": "flip", "target": "off"}]},
        "off": {"transitions": [{"event": "flip", "target": "on"}]},
    },
}

SCXML_DOC = (
    '<?xml version="1.0"?>'
    '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1" name="Demo">'
    '<state id="s1"><transition event="go" target="s2"/></state>'
    '<final id="s2"/></scxml>'
)


class TestInlineContent:
    def test_json_inline(self):
        cls = load(json.dumps(TOGGLE_NATIVE), format="json")
        assert issubclass(cls, StateChart)
        sm = cls()
        assert "on" in sm.configuration_values
        sm.send("flip")
        assert "off" in sm.configuration_values

    def test_yaml_inline(self):
        text = (
            "states:\n"
            "  a:\n"
            "    initial: true\n"
            "    transitions:\n"
            "      - {event: go, target: b}\n"
            "  b: {}\n"
        )
        cls = load(text, format="yaml")
        sm = cls()
        sm.send("go")
        assert "b" in sm.configuration_values

    def test_scxml_inline(self):
        sm = load(SCXML_DOC, format="scxml")()
        sm.send("go")
        assert "s2" in sm.configuration_values

    def test_inline_without_format_raises(self):
        with pytest.raises(ValueError, match="Cannot detect format"):
            load(json.dumps(TOGGLE_NATIVE))

    def test_name_override(self):
        cls = load(json.dumps(TOGGLE_NATIVE), format="json", name="Custom")
        assert cls.__name__ == "Custom"


class TestFileSources:
    def test_load_json_file(self, tmp_path):
        path = tmp_path / "toggle.json"
        path.write_text(json.dumps(TOGGLE_NATIVE))
        cls = load(path)  # Path, format detected by extension
        assert cls().send  # instantiable
        # also accept a string path
        cls2 = load(str(path))
        assert issubclass(cls2, StateChart)

    def test_load_yaml_file(self, tmp_path):
        path = tmp_path / "m.yaml"
        path.write_text("states:\n  a: {initial: true}\n")
        assert issubclass(load(path), StateChart)

    def test_load_scxml_file_changes_cwd(self, tmp_path):
        path = tmp_path / "demo.scxml"
        path.write_text(SCXML_DOC)
        sm = load(path)()
        sm.send("go")
        assert "s2" in sm.configuration_values


class TestSecurity:
    def test_safe_by_default_rejects_arbitrary_python(self):
        doc = {
            "states": {
                "s": {
                    "initial": True,
                    "transitions": [{"event": "go", "cond": "__import__('os')", "target": "s"}],
                }
            }
        }
        with pytest.raises(InvalidDefinition):
            load(json.dumps(doc), format="json")

    def test_trusted_enables_python_expressions(self):
        doc = {
            "states": {
                "s": {
                    "initial": True,
                    "transitions": [{"event": "go", "cond": "len(items) > 0", "target": "t"}],
                },
                "t": {"final": True},
            }
        }
        cls = load(json.dumps(doc), format="json", trusted=True)

        class Model:
            def __init__(self):
                self.items = [1]

        sm = cls(model=Model())
        sm.send("go")
        assert "t" in sm.configuration_values


class TestValidation:
    def test_validate_valid_document(self):
        cls = load(json.dumps(TOGGLE_NATIVE), format="json", validate=True)
        assert issubclass(cls, StateChart)

    def test_validate_rejects_invalid_document(self):
        bad = {"states": {"a": {"initial": True, "unexpected": 1}}}
        with pytest.raises(InvalidDefinition, match="failed schema validation"):
            load(json.dumps(bad), format="json", validate=True)

    def test_validate_not_supported_for_scxml(self):
        with pytest.raises(ValueError, match="not supported for the 'scxml' format"):
            load(SCXML_DOC, format="scxml", validate=True)


class TestProcessorAccess:
    def test_returned_class_keeps_processor(self):
        cls = load(json.dumps(TOGGLE_NATIVE), format="json")
        assert cls._io_processor is not None
        assert "Toggle" in cls._io_processor.scs

    def test_build_processor_low_level(self):
        proc = build_processor(SCXML_DOC, format="scxml")
        assert "Demo" in proc.scs
        sm = proc.start()
        sm.send("go")
        assert "s2" in sm.configuration_values
