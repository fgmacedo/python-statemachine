"""Tests for the native (JSON/YAML) dict -> IR translator."""

import pytest
from statemachine.exceptions import InvalidDefinition
from statemachine.io import model
from statemachine.io.native import _flag
from statemachine.io.native import native_dict_to_definition


def defn(doc):
    return native_dict_to_definition(doc)


class TestTopLevel:
    def test_minimal(self):
        d = defn({"name": "M", "states": {"a": {"initial": True}}})
        assert d.name == "M"
        assert d.initial_states == ["a"]

    def test_name_from_source_when_absent(self):
        d = native_dict_to_definition({"states": {"a": {}}}, source_name="from_file")
        assert d.name == "from_file"

    def test_first_state_is_initial_when_none_declared(self):
        d = defn({"states": {"a": {}, "b": {}}})
        assert d.initial_states == ["a"]
        assert d.states["a"].initial is True

    def test_not_a_mapping(self):
        with pytest.raises(InvalidDefinition, match="must be a mapping"):
            native_dict_to_definition([1, 2, 3])

    def test_missing_states(self):
        with pytest.raises(InvalidDefinition, match="non-empty 'states'"):
            defn({"name": "x"})

    def test_empty_states(self):
        with pytest.raises(InvalidDefinition, match="non-empty 'states'"):
            defn({"states": {}})


class TestState:
    def test_flags_and_nested(self):
        d = defn(
            {
                "states": {
                    "p": {
                        "parallel": True,
                        "states": {"a": {"initial": True}, "b": {"final": True}},
                    }
                }
            }
        )
        p = d.states["p"]
        assert p.parallel
        assert p.states["a"].initial
        assert p.states["b"].final

    def test_state_not_mapping(self):
        with pytest.raises(InvalidDefinition, match="must be a mapping"):
            defn({"states": {"a": [1]}})

    def test_history(self):
        d = defn(
            {
                "states": {
                    "c": {
                        "states": {"a": {"initial": True}},
                        "history": {"h": {"type": "deep", "transitions": [{"target": "a"}]}},
                    }
                }
            }
        )
        hist = d.states["c"].history["h"]
        assert hist.type == "deep"
        assert hist.transitions[0].target == "a"

    def test_donedata_only_on_final(self):
        d = defn(
            {
                "states": {
                    "done": {
                        "final": True,
                        "donedata": {"params": [{"name": "x", "expr": "1"}], "content": "c"},
                    },
                    "other": {"initial": True, "donedata": {"content": "ignored"}},
                }
            }
        )
        assert d.states["done"].donedata.params[0].name == "x"
        # donedata on a non-final state is ignored
        assert d.states["other"].donedata is None


class TestActions:
    def test_enter_exit_content_and_refs(self):
        d = defn(
            {
                "states": {
                    "a": {
                        "initial": True,
                        "enter": [{"assign": {"location": "x", "expr": "1"}}, "my_enter_method"],
                        "exit": "my_exit_method",
                    }
                }
            }
        )
        a = d.states["a"]
        assert isinstance(a.onentry[0].actions[0], model.AssignAction)
        assert a.enter_refs == ["my_enter_method"]
        assert a.exit_refs == ["my_exit_method"]
        assert a.onexit == []  # pure ref, no executable content

    def test_all_structured_actions(self):
        actions = [
            {"assign": {"location": "x", "expr": "1"}},
            {"raise": "ev"},
            {"raise": {"event": "ev2"}},
            {"log": "msg"},
            {"log": {"label": "L", "expr": "v"}},
            {"send": {"event": "e", "params": [{"name": "p", "expr": "1"}]}},
            {"cancel": {"sendid": "s1"}},
            {"foreach": {"array": "items", "item": "i", "do": [{"log": "x"}]}},
            {
                "if": {
                    "cond": "a",
                    "then": [{"log": "t"}],
                    "elif": [{"cond": "b", "then": [{"log": "e"}]}],
                    "else": [{"log": "f"}],
                }
            },
        ]
        d = defn({"states": {"a": {"initial": True, "enter": actions}}})
        kinds = [type(x).__name__ for x in d.states["a"].onentry[0].actions]
        assert kinds == [
            "AssignAction",
            "RaiseAction",
            "RaiseAction",
            "LogAction",
            "LogAction",
            "SendAction",
            "CancelAction",
            "ForeachAction",
            "IfAction",
        ]
        if_action = d.states["a"].onentry[0].actions[-1]
        assert [b.cond for b in if_action.branches] == ["a", "b", None]

    def test_script_action_node(self):
        d = defn({"states": {"a": {"initial": True, "enter": [{"script": "x = 1"}]}}})
        assert isinstance(d.states["a"].onentry[0].actions[0], model.ScriptAction)

    def test_structured_exit_content(self):
        d = defn({"states": {"a": {"initial": True, "exit": [{"log": "bye"}]}}})
        assert isinstance(d.states["a"].onexit[0].actions[0], model.LogAction)

    def test_if_without_else(self):
        d = defn(
            {
                "states": {
                    "a": {
                        "initial": True,
                        "enter": [{"if": {"cond": "x", "then": [{"log": "t"}]}}],
                    }
                }
            }
        )
        if_action = d.states["a"].onentry[0].actions[0]
        assert [b.cond for b in if_action.branches] == ["x"]

    def test_unknown_action_key(self):
        with pytest.raises(InvalidDefinition, match="exactly one"):
            defn({"states": {"a": {"initial": True, "enter": [{"bogus": 1}]}}})

    def test_two_action_keys(self):
        with pytest.raises(InvalidDefinition, match="exactly one"):
            defn({"states": {"a": {"initial": True, "enter": [{"raise": "x", "log": "y"}]}}})

    def test_action_wrong_type(self):
        with pytest.raises(InvalidDefinition, match="string or a mapping"):
            defn({"states": {"a": {"initial": True, "enter": [123]}}})

    def test_refs_not_allowed_in_if(self):
        with pytest.raises(InvalidDefinition, match="not allowed inside"):
            defn(
                {
                    "states": {
                        "a": {"initial": True, "enter": [{"if": {"cond": "c", "then": ["a_ref"]}}]}
                    }
                }
            )

    def test_as_list_wrong_type(self):
        with pytest.raises(InvalidDefinition, match="Expected an action"):
            defn({"states": {"a": {"initial": True, "enter": 3.14}}})


class TestTransitions:
    def test_eventless_and_event(self):
        d = defn(
            {
                "states": {
                    "a": {
                        "initial": True,
                        "transitions": [
                            {"event": "go", "target": "b"},
                            {"target": "c", "cond": "x > 0"},  # eventless
                        ],
                    },
                    "b": {},
                    "c": {},
                }
            }
        )
        ts = d.states["a"].transitions
        assert ts[0].event == "go"
        assert ts[1].event is None
        assert ts[1].cond == "x > 0"

    def test_transition_on_content_and_refs(self):
        d = defn(
            {
                "states": {
                    "a": {
                        "initial": True,
                        "transitions": [
                            {
                                "event": "go",
                                "target": "a",
                                "on": [{"assign": {"location": "x", "expr": "1"}}, "after_ref"],
                                "before": "before_ref",
                                "after": ["after1", "after2"],
                                "unless": "blocked",
                            }
                        ],
                    }
                }
            }
        )
        t = d.states["a"].transitions[0]
        assert isinstance(t.on.actions[0], model.AssignAction)
        assert t.on_refs == ["after_ref"]
        assert t.before_refs == ["before_ref"]
        assert t.before is None
        assert t.after_refs == ["after1", "after2"]
        assert t.after is None
        assert t.unless == "blocked"

    def test_before_after_accept_structured_actions_and_refs(self):
        d = defn(
            {
                "states": {
                    "a": {
                        "initial": True,
                        "transitions": [
                            {
                                "event": "go",
                                "target": "a",
                                "before": [{"assign": {"location": "x", "expr": "1"}}, "ref"],
                                "after": {"log": "done"},
                            }
                        ],
                    }
                }
            }
        )
        t = d.states["a"].transitions[0]
        assert isinstance(t.before.actions[0], model.AssignAction)
        assert t.before_refs == ["ref"]
        assert isinstance(t.after.actions[0], model.LogAction)
        assert t.after_refs == []

    def test_transition_not_mapping(self):
        with pytest.raises(InvalidDefinition, match="Transition must be a mapping"):
            defn({"states": {"a": {"initial": True, "transitions": ["nope"]}}})

    def test_before_action_must_be_string_or_mapping(self):
        with pytest.raises(InvalidDefinition, match="must be a string or a mapping"):
            defn(
                {
                    "states": {
                        "a": {
                            "initial": True,
                            "transitions": [{"event": "g", "target": "a", "before": [1]}],
                        }
                    }
                }
            )


class TestDatamodel:
    def test_list_form(self):
        d = defn({"datamodel": [{"id": "x", "expr": "1"}], "states": {"a": {}}})
        assert d.datamodel.data[0].id == "x"

    def test_mapping_form(self):
        d = defn({"datamodel": {"x": "1", "y": "2"}, "states": {"a": {}}})
        ids = {item.id for item in d.datamodel.data}
        assert ids == {"x", "y"}

    def test_absent(self):
        assert defn({"states": {"a": {}}}).datamodel is None


class TestFlag:
    @pytest.mark.parametrize("value", [True, "true", "yes", "on", "1", "TRUE"])
    def test_truthy(self, value):
        assert _flag(value) is True

    @pytest.mark.parametrize("value", [False, "false", "no", "off", "0", "", None])
    def test_falsy(self, value):
        assert _flag(value) is False

    def test_invalid_string(self):
        with pytest.raises(InvalidDefinition, match="boolean flag"):
            _flag("maybe")


class TestStrictKeys:
    """Unknown keys are rejected at parse time, matching the schema's strictness."""

    def test_unknown_document_key(self):
        with pytest.raises(InvalidDefinition, match="Unknown document key"):
            defn({"states": {"a": {"initial": True}}, "bogus": 1})

    def test_unknown_state_key(self):
        with pytest.raises(InvalidDefinition, match="Unknown state 'a' key"):
            defn({"states": {"a": {"initial": True, "bogus": 1}}})

    def test_unknown_transition_key(self):
        with pytest.raises(InvalidDefinition, match="Unknown transition key"):
            defn({"states": {"a": {"initial": True, "transitions": [{"target": "a", "bad": 1}]}}})

    def test_unknown_invoke_key(self):
        with pytest.raises(InvalidDefinition, match="Unknown invoke key"):
            defn({"states": {"a": {"initial": True, "invoke": {"src": "c.yaml", "bad": 1}}}})
