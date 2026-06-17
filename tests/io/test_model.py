"""Tests for the neutral IR dataclasses."""

from statemachine.io import model


def test_executable_content_is_empty():
    assert model.ExecutableContent().is_empty
    assert not model.ExecutableContent(actions=[model.RaiseAction(event="e")]).is_empty


def test_dataitem_src_is_plain_string():
    item = model.DataItem(id="x", src="file:data.json", expr=None, content=None)
    assert item.src == "file:data.json"


def test_state_defaults_include_native_ref_fields():
    state = model.State(id="a")
    assert state.enter_refs == []
    assert state.exit_refs == []
    assert state.onentry == []


def test_transition_defaults_include_native_fields():
    t = model.Transition()
    assert t.on_refs == []
    assert t.before is None
    assert t.before_refs == []
    assert t.after is None
    assert t.after_refs == []
    assert t.unless is None


def test_action_str_helpers():
    assert str(model.RaiseAction(event="e")) == "RaiseAction"
    branch = model.IfBranch(cond=None)
    assert str(branch) == "<empty cond>"
    branch.append(model.RaiseAction(event="e"))
    assert len(branch.actions) == 1
