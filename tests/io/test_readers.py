"""Tests for the JSON and YAML format readers."""

from statemachine.io.json.reader import JSONReader
from statemachine.io.scxml.reader import SCXMLReader
from statemachine.io.yaml.reader import YAMLReader


class TestJSONReader:
    def test_parse_and_read(self):
        reader = JSONReader()
        text = '{"name": "J", "states": {"a": {"initial": true}}}'
        assert reader.parse_document(text)["name"] == "J"
        definition = reader.read(text, source_name="fallback")
        assert definition.name == "J"

    def test_source_name_fallback(self):
        definition = JSONReader().read('{"states": {"a": {}}}', source_name="fallback")
        assert definition.name == "fallback"


class TestYAMLReader:
    def test_parse_and_read(self):
        text = "name: Y\nstates:\n  a:\n    initial: true\n"
        definition = YAMLReader().read(text)
        assert definition.name == "Y"

    def test_on_off_keys_are_strings_not_booleans(self):
        # YAML 1.1 would coerce on/off/yes/no to booleans; our loader must not.
        text = "states:\n  off:\n    initial: true\n  on: {}\n"
        doc = YAMLReader().parse_document(text)
        assert set(doc["states"]) == {"off", "on"}

    def test_true_false_still_booleans(self):
        doc = YAMLReader().parse_document("states:\n  a:\n    initial: true\n    final: false\n")
        assert doc["states"]["a"]["initial"] is True
        assert doc["states"]["a"]["final"] is False

    def test_loader_is_cached(self):
        import statemachine.io.yaml.reader as mod

        mod._LOADER = None
        first = YAMLReader().parse_document("states: {a: {}}")
        cached = mod._LOADER
        second = YAMLReader().parse_document("states: {b: {}}")
        assert cached is mod._LOADER
        assert first == {"states": {"a": {}}}
        assert second == {"states": {"b": {}}}


class TestSCXMLReader:
    def test_read_returns_definition(self):
        scxml = (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s" name="X">'
            '<final id="s"/></scxml>'
        )
        definition = SCXMLReader().read(scxml)
        assert definition.name == "X"
        assert "s" in definition.states
