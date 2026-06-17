"""Tests for the JSON Schema and the optional validation helper."""

import json
from pathlib import Path

import pytest
from statemachine.exceptions import InvalidDefinition
from statemachine.io import native
from statemachine.io.native import _ACTION_KEYS
from statemachine.io.validation import load_schema
from statemachine.io.validation import validate_document
from statemachine.io.yaml.reader import YAMLReader

# Every native (.yaml/.json) document used anywhere in the test suite, so the schema is
# checked against the full corpus of examples and cannot silently fall behind the runtime.
TESTS_IO = Path(__file__).parent


class TestSchema:
    def test_schema_is_loadable_and_packaged(self):
        # Loaded via importlib.resources — proves the .json ships with the package.
        schema = load_schema()
        assert schema["$id"].endswith("statechart/v1.json")
        assert "states" in schema["properties"]

    def test_schema_is_cached(self):
        assert load_schema() is load_schema()

    def test_action_vocabulary_matches_parser(self):
        # The parser uses ``_ACTION_KEYS`` as the authoritative action vocabulary, so the
        # schema's structured-action keys must equal it — a new action can't be added to one
        # side without the other.
        schema = load_schema()
        schema_keys = set(schema["$defs"]["structuredAction"]["properties"])
        assert schema_keys == _ACTION_KEYS

    @pytest.mark.parametrize(
        ("parser_keys", "schema_pointer"),
        [
            (native._DOCUMENT_KEYS, ("properties",)),
            (native._STATE_KEYS, ("$defs", "state", "properties")),
            (native._TRANSITION_KEYS, ("$defs", "transition", "properties")),
            (native._INVOKE_KEYS, ("$defs", "invoke", "properties")),
        ],
    )
    def test_node_vocabulary_matches_parser(self, parser_keys, schema_pointer):
        # Each container node's accepted keys (the parser's source of truth) must equal the
        # schema's allowed properties: drift on either side breaks the build.
        node = load_schema()
        for key in schema_pointer:
            node = node[key]
        assert set(parser_keys) == set(node)


class TestValidateDocument:
    def test_valid(self):
        validate_document({"name": "M", "states": {"a": {"initial": True, "transitions": []}}})

    def test_valid_with_actions(self):
        validate_document(
            {
                "states": {
                    "a": {
                        "initial": True,
                        "enter": [{"assign": {"location": "x", "expr": "1"}}],
                        "transitions": [{"event": "go", "target": "a", "cond": "x > 0"}],
                    }
                }
            }
        )

    def test_valid_before_after_structured_actions(self):
        # before/after accept the full action vocabulary (refs + structured + script),
        # matching the runtime — not just callback-reference strings.
        validate_document(
            {
                "states": {
                    "a": {
                        "initial": True,
                        "transitions": [
                            {
                                "event": "go",
                                "target": "a",
                                "before": [{"assign": {"location": "x", "expr": "1"}}, "ref"],
                                "after": {"script": "x = 2"},
                            }
                        ],
                    }
                }
            }
        )

    def test_valid_invoke_inline_content_and_src(self):
        validate_document(
            {
                "states": {
                    "a": {
                        "initial": True,
                        "invoke": [
                            {"content": {"states": {"r": {"initial": True}}}, "id": "c1"},
                            {"src": "child.yaml", "autoforward": True},
                        ],
                        "transitions": [{"event": "done", "target": "b"}],
                    },
                    "b": {"final": True},
                }
            }
        )

    def test_valid_invoke_single_object(self):
        validate_document({"states": {"a": {"initial": True, "invoke": {"src": "child.yaml"}}}})

    def test_valid_history_donedata_send_params_foreach_if(self):
        validate_document(
            {
                "states": {
                    "a": {
                        "initial": True,
                        "history": {"h": {"type": "deep"}},
                        "enter": [
                            {"foreach": {"array": "xs", "item": "i", "do": [{"log": "i"}]}},
                            {
                                "if": {
                                    "cond": "x",
                                    "then": [{"raise": "e"}],
                                    "elif": [{"cond": "y", "then": [{"raise": "f"}]}],
                                    "else": [{"raise": "g"}],
                                }
                            },
                        ],
                        "transitions": [
                            {
                                "event": "g",
                                "target": "f",
                                "on": {
                                    "send": {"event": "e", "params": [{"name": "p", "expr": "1"}]}
                                },
                            }
                        ],
                    },
                    "f": {"final": True, "donedata": {"params": [{"name": "r", "expr": "1"}]}},
                }
            }
        )

    def test_invalid_extra_key(self):
        with pytest.raises(InvalidDefinition, match="failed schema validation"):
            validate_document({"states": {"a": {"bogus": 1}}})

    def test_invalid_missing_states(self):
        with pytest.raises(InvalidDefinition, match="failed schema validation"):
            validate_document({"name": "x"})

    def test_invalid_callback_ref_in_nested_action_list(self):
        # Nested action lists (foreach `do`, if `then`/`else`, invoke `finalize`) are
        # structured-only; a bare string ref is rejected, matching the parser.
        with pytest.raises(InvalidDefinition, match="failed schema validation"):
            validate_document(
                {
                    "states": {
                        "a": {
                            "initial": True,
                            "enter": [{"foreach": {"array": "xs", "item": "i", "do": ["ref"]}}],
                        }
                    }
                }
            )

    def test_invalid_invoke_extra_key(self):
        with pytest.raises(InvalidDefinition, match="failed schema validation"):
            validate_document({"states": {"a": {"initial": True, "invoke": {"bogus": 1}}}})


def _native_fixture_docs():
    paths = sorted(TESTS_IO.rglob("*.yaml")) + sorted(TESTS_IO.rglob("*.json"))
    cases = []
    for path in paths:
        if path.suffix == ".json":
            doc = json.loads(path.read_text())
        else:
            doc = YAMLReader().parse_document(path.read_text())
        cases.append(pytest.param(doc, id=str(path.relative_to(TESTS_IO))))
    return cases


class TestFixturesValidateAgainstSchema:
    """Every native fixture in the suite must be schema-valid, keeping schema and runtime
    in sync: a runtime feature exercised by a fixture but missing from the schema fails here."""

    @pytest.mark.parametrize("doc", _native_fixture_docs())
    def test_native_fixture_is_schema_valid(self, doc):
        validate_document(doc)
