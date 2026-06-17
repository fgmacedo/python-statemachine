"""Tests for the format-neutral Interpreter (runtime)."""

import pytest
from statemachine.exceptions import InvalidDefinition
from statemachine.io import model
from statemachine.io.evaluators import evaluator_for
from statemachine.io.interpreter import Interpreter
from statemachine.io.invoke import Invoker
from statemachine.io.json.reader import JSONReader
from statemachine.io.native import native_dict_to_definition


def build(doc, *, trusted=False):
    interpreter = Interpreter(reader=JSONReader(), evaluator=evaluator_for(trusted))
    definition = native_dict_to_definition(doc)
    interpreter.process_definition(definition, location=definition.name or "sc")
    return interpreter


class TestRuntimeHooks:
    def test_initial_enter_prefix_empty_when_not_invoked(self):
        interp = Interpreter(reader=JSONReader(), evaluator=evaluator_for())
        assert interp.initial_enter_prefix(is_invoked=False) == []

    def test_initial_enter_prefix_has_invoke_init_when_invoked(self):
        interp = Interpreter(reader=JSONReader(), evaluator=evaluator_for())
        prefix = interp.initial_enter_prefix(is_invoked=True)
        assert len(prefix) == 1
        assert callable(prefix[0])

    def test_make_invoker_returns_invoker(self):
        interp = Interpreter(reader=JSONReader(), evaluator=evaluator_for())
        invoker = interp.make_invoker(model.InvokeDefinition())
        assert isinstance(invoker, Invoker)


class TestBuildAndRun:
    def test_guard_list_and_actions(self):
        interp = build(
            {
                "name": "G",
                "datamodel": [{"id": "x", "expr": "5"}, {"id": "y", "expr": "0"}],
                "states": {
                    "a": {
                        "initial": True,
                        "transitions": [
                            {"event": "go", "target": "b", "cond": ["x > 0", "x < 10"]},
                        ],
                    },
                    "b": {"final": True},
                },
            }
        )
        sm = interp.start()
        sm.send("go")
        assert "b" in sm.configuration_values

    def test_enter_exit_refs_invoke_model_methods(self):
        interp = build(
            {
                "name": "R",
                "states": {
                    "a": {
                        "initial": True,
                        "enter": "mark_enter",
                        "exit": "mark_exit",
                        "transitions": [{"event": "go", "target": "b"}],
                    },
                    "b": {"final": True},
                },
            }
        )

        class Model:
            def __init__(self):
                self.events = []

            def mark_enter(self):
                self.events.append("enter")

            def mark_exit(self):
                self.events.append("exit")

        m = Model()
        sm = interp.start(model=m)
        sm.send("go")
        assert m.events == ["enter", "exit"]

    def test_unless_blocks_transition(self):
        interp = build(
            {
                "name": "U",
                "datamodel": [{"id": "blocked", "expr": "True"}],
                "states": {
                    "a": {
                        "initial": True,
                        "transitions": [{"event": "go", "target": "b", "unless": "blocked"}],
                    },
                    "b": {"final": True},
                },
            }
        )
        sm = interp.start()
        sm.send("go")
        assert "a" in sm.configuration_values  # unless=blocked True -> not allowed

    def test_before_and_after_refs(self):
        interp = build(
            {
                "name": "BA",
                "states": {
                    "a": {
                        "initial": True,
                        "transitions": [
                            {"event": "go", "target": "b", "before": "pre", "after": "post"}
                        ],
                    },
                    "b": {"final": True},
                },
            }
        )

        class Model:
            def __init__(self):
                self.calls = []

            def pre(self):
                self.calls.append("before")

            def post(self):
                self.calls.append("after")

        m = Model()
        sm = interp.start(model=m)
        sm.send("go")
        assert m.calls == ["before", "after"]

    def test_before_after_structured_actions_and_script(self):
        # `before`/`after` accept the same vocabulary as `on`: structured actions and,
        # under trusted, a `script` running arbitrary Python — mixed with callback refs.
        interp = build(
            {
                "name": "BAS",
                "datamodel": [{"id": "trail", "expr": "[]"}],
                "states": {
                    "a": {
                        "initial": True,
                        "transitions": [
                            {
                                "event": "go",
                                "target": "b",
                                "before": [
                                    {"assign": {"location": "trail", "expr": "trail + ['b']"}},
                                    "mark",
                                ],
                                "on": {"assign": {"location": "trail", "expr": "trail + ['o']"}},
                                "after": {"script": "trail = trail + ['a']"},
                            }
                        ],
                    },
                    "b": {"final": True},
                },
            },
            trusted=True,
        )

        class Model:
            def __init__(self):
                self.refs = []

            def mark(self):
                self.refs.append("ref")

        m = Model()
        sm = interp.start(model=m)
        sm.send("go")
        assert sm.model.trail == ["b", "o", "a"]
        assert m.refs == ["ref"]

    def test_script_in_before_rejected_when_not_trusted(self):
        with pytest.raises(InvalidDefinition, match="<script>"):
            build(
                {
                    "name": "NS",
                    "states": {
                        "a": {
                            "initial": True,
                            "transitions": [
                                {"event": "go", "target": "b", "before": {"script": "x = 1"}}
                            ],
                        },
                        "b": {"final": True},
                    },
                }
            )

    def test_on_content_and_ref_combined(self):
        interp = build(
            {
                "name": "C",
                "datamodel": [{"id": "x", "expr": "0"}],
                "states": {
                    "a": {
                        "initial": True,
                        "transitions": [
                            {
                                "event": "go",
                                "target": "b",
                                "on": [{"assign": {"location": "x", "expr": "1"}}, "note"],
                            }
                        ],
                    },
                    "b": {"final": True},
                },
            }
        )

        class Model:
            def __init__(self):
                self.x = 0
                self.noted = False

            def note(self):
                self.noted = True

        m = Model()
        sm = interp.start(model=m)
        sm.send("go")
        assert m.x == 1
        assert m.noted is True


class TestSystemVariablesNative:
    """System variables (_event/_sessionid/_name) are available to native formats too."""

    def test_event_name_in_guard(self):
        interp = build(
            {
                "name": "SV",
                "datamodel": [{"id": "seen", "expr": "''"}],
                "states": {
                    "a": {
                        "initial": True,
                        "transitions": [
                            {
                                "event": "go",
                                "target": "b",
                                "on": [{"assign": {"location": "seen", "expr": "_event.name"}}],
                            }
                        ],
                    },
                    "b": {"final": True},
                },
            }
        )
        sm = interp.start()
        sm.send("go")
        assert sm.model.seen == "go"
