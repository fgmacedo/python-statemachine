"""Native (YAML/JSON) ``invoke`` support: functional parity with SCXML."""

import time

import pytest
from statemachine.exceptions import InvalidDefinition
from statemachine.io import load
from statemachine.io import model
from statemachine.io.native import native_dict_to_definition


def _wait_final(sm, timeout: float = 3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(s.final for s in sm.configuration):
            return
        time.sleep(0.01)


INLINE_PARENT = """
name: Parent
states:
  waiting:
    initial: true
    invoke:
      - content:
          name: Child
          states:
            running:
              initial: true
              enter:
                - send: {event: from_child, target: "#_parent"}
    transitions:
      - event: from_child
        target: done
  done:
    final: true
"""


class TestNativeInvokeRuntime:
    def test_inline_child_sends_to_parent(self):
        sm = load(INLINE_PARENT, format="yaml")()
        _wait_final(sm)
        assert "done" in sm.configuration_values

    def test_invoke_via_src_file(self, tmp_path):
        (tmp_path / "child.yaml").write_text(
            "name: Child\n"
            "states:\n"
            "  running:\n"
            "    initial: true\n"
            "    enter:\n"
            '      - send: {event: from_child, target: "#_parent"}\n'
        )
        parent = (
            "name: Parent\n"
            "states:\n"
            "  waiting:\n"
            "    initial: true\n"
            "    invoke:\n"
            "      - src: child.yaml\n"
            "    transitions:\n"
            "      - {event: from_child, target: done}\n"
            "  done:\n"
            "    final: true\n"
        )
        path = tmp_path / "parent.yaml"
        path.write_text(parent)
        sm = load(path)()
        _wait_final(sm)
        assert "done" in sm.configuration_values


class TestNativeInvokeParsing:
    def test_inline_content_becomes_definition(self):
        d = native_dict_to_definition(
            {
                "states": {
                    "s": {
                        "initial": True,
                        "invoke": [{"id": "c", "content": {"states": {"x": {"initial": True}}}}],
                    }
                }
            }
        )
        inv = d.states["s"].invocations[0]
        assert inv.id == "c"
        assert isinstance(inv.content, model.StateMachineDefinition)
        assert "x" in inv.content.states

    def test_single_mapping_and_fields(self):
        d = native_dict_to_definition(
            {
                "states": {
                    "s": {
                        "initial": True,
                        "invoke": {
                            "src": "child.yaml",
                            "id": "c1",
                            "autoforward": True,
                            "namelist": "a b",
                            "params": [{"name": "p", "expr": "1"}],
                            "finalize": [{"assign": {"location": "x", "expr": "2"}}],
                        },
                    }
                }
            }
        )
        inv = d.states["s"].invocations[0]
        assert inv.src == "child.yaml"
        assert inv.autoforward is True
        assert inv.namelist == "a b"
        assert inv.params[0].name == "p"
        assert inv.finalize is not None
        assert not inv.finalize.is_empty

    def test_no_finalize(self):
        d = native_dict_to_definition(
            {"states": {"s": {"initial": True, "invoke": {"src": "c.yaml"}}}}
        )
        assert d.states["s"].invocations[0].finalize is None

    def test_invoke_entry_not_mapping(self):
        with pytest.raises(InvalidDefinition, match="Invoke entry must be a mapping"):
            native_dict_to_definition({"states": {"s": {"initial": True, "invoke": ["nope"]}}})
