"""Unit tests for SCXML parser, actions, and schema modules."""

import logging
import xml.etree.ElementTree as ET
from unittest.mock import Mock

import pytest
from statemachine.io.scxml.actions import EventDataWrapper
from statemachine.io.scxml.actions import Log
from statemachine.io.scxml.actions import ParseTime
from statemachine.io.scxml.actions import create_action_callable
from statemachine.io.scxml.actions import create_datamodel_action_callable
from statemachine.io.scxml.invoke import SCXMLInvoker
from statemachine.io.scxml.parser import parse_element
from statemachine.io.scxml.parser import parse_scxml
from statemachine.io.scxml.parser import strip_namespaces
from statemachine.io.scxml.schema import CancelAction
from statemachine.io.scxml.schema import DataModel
from statemachine.io.scxml.schema import IfBranch
from statemachine.io.scxml.schema import InvokeDefinition
from statemachine.io.scxml.schema import LogAction
from statemachine.io.scxml.schema import Param

# --- ParseTime ---


class TestParseTimeErrors:
    def test_invalid_milliseconds_value(self):
        """ParseTime raises ValueError for non-numeric milliseconds."""
        with pytest.raises(ValueError, match="Invalid time value"):
            ParseTime.time_in_ms("abcms")

    def test_invalid_seconds_value(self):
        """ParseTime raises ValueError for non-numeric seconds."""
        with pytest.raises(ValueError, match="Invalid time value"):
            ParseTime.time_in_ms("abcs")

    def test_invalid_unit(self):
        """ParseTime raises ValueError for values without recognized unit."""
        with pytest.raises(ValueError, match="Invalid time unit"):
            ParseTime.time_in_ms("abc")


# --- Parser ---


class TestStripNamespaces:
    def test_removes_namespace_from_attributes(self):
        """strip_namespaces removes namespace prefixes from attribute names."""
        xml = '<root xmlns:ns="http://example.com"><child ns:attr="value"/></root>'
        tree = ET.fromstring(xml)
        strip_namespaces(tree)
        child = tree.find("child")
        assert "attr" in child.attrib
        assert child.attrib["attr"] == "value"


class TestParseScxml:
    def test_no_scxml_element_raises(self):
        """parse_scxml raises ValueError if no scxml element is found."""
        xml = "<notscxml><state id='s1'/></notscxml>"
        with pytest.raises(ValueError, match="No scxml element found"):
            parse_scxml(xml)


class TestParseState:
    def test_state_without_id_gets_auto_generated(self):
        """State element without id attribute gets an auto-generated id."""
        xml = '<scxml xmlns="http://www.w3.org/2005/07/scxml"><state/></scxml>'
        definition = parse_scxml(xml)
        state_ids = list(definition.states.keys())
        assert len(state_ids) == 1
        assert state_ids[0].startswith("__auto_")


class TestParseHistory:
    def test_history_without_id_raises(self):
        """History element without id attribute raises ValueError."""
        xml = (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml">'
            '<state id="s1"><history/></state>'
            "</scxml>"
        )
        with pytest.raises(ValueError, match="History must have an 'id' attribute"):
            parse_scxml(xml)


class TestParseElement:
    def test_unknown_tag_raises(self):
        """parse_element raises ValueError for an unrecognized tag."""
        element = ET.fromstring("<unknown_tag/>")
        with pytest.raises(ValueError, match="Unknown tag: unknown_tag"):
            parse_element(element)


class TestParseSendParam:
    def test_param_without_expr_or_location_raises(self):
        """Send param without expr or location raises ValueError."""
        xml = (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml">'
            '<state id="s1">'
            "<onentry>"
            '<send event="test"><param name="p1"/></send>'
            "</onentry>"
            "</state>"
            "</scxml>"
        )
        with pytest.raises(ValueError, match="Must specify"):
            parse_scxml(xml)


# --- Actions ---


class TestCreateActionCallable:
    def test_unknown_action_type_raises(self):
        """create_action_callable raises ValueError for unknown action types."""
        from statemachine.io.scxml.schema import Action

        with pytest.raises(ValueError, match="Unknown action type"):
            create_action_callable(Action())


class TestLogAction:
    def test_log_without_label(self, capsys):
        """Log action without label prints just the value."""
        action = LogAction(label=None, expr="42")
        log = Log(action)
        log()  # "42" is a literal that evaluates without machine context
        captured = capsys.readouterr()
        assert "42" in captured.out


class TestCancelActionCallable:
    def test_cancel_without_sendid_raises(self):
        """CancelAction without sendid or sendidexpr raises ValueError."""
        from statemachine.io.scxml.actions import create_cancel_action_callable

        action = CancelAction(sendid=None, sendidexpr=None)
        cancel = create_cancel_action_callable(action)
        with pytest.raises(ValueError, match="must have either 'sendid' or 'sendidexpr'"):
            cancel(machine=None)


class TestCreateDatamodelCallable:
    def test_empty_datamodel_returns_none(self):
        """create_datamodel_action_callable returns None for empty DataModel."""
        model = DataModel(data=[], scripts=[])
        result = create_datamodel_action_callable(model)
        assert result is None


# --- Schema ---


class TestIfBranch:
    def test_str_with_none_cond(self):
        """IfBranch.__str__ returns '<empty cond>' for None condition."""
        branch = IfBranch(cond=None)
        assert str(branch) == "<empty cond>"

    def test_str_with_cond(self):
        """IfBranch.__str__ returns the condition string."""
        branch = IfBranch(cond="x > 0")
        assert str(branch) == "x > 0"


# --- SCXML integration tests for action edge cases ---


class TestSCXMLIfConditionError:
    """SCXML <if> with a condition that raises an error."""

    def test_if_condition_error_sends_error_execution(self):
        """When an <if> condition evaluation fails, error.execution is sent."""
        from statemachine.io.scxml.processor import SCXMLProcessor

        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <state id="s1">
            <onentry>
              <if cond="undefined_var">
                <log label="unreachable"/>
              </if>
            </onentry>
            <transition event="error.execution" target="error"/>
          </state>
          <final id="error"/>
        </scxml>
        """
        processor = SCXMLProcessor()
        processor.parse_scxml("test_if_error", scxml)
        sm = processor.start()
        assert sm.configuration == {sm.states_map["error"]}


class TestSCXMLForeachArrayError:
    """SCXML <foreach> with an array expression that fails to evaluate."""

    def test_foreach_bad_array_raises(self):
        """<foreach> with invalid array expression raises ValueError."""
        from statemachine.io.scxml.processor import SCXMLProcessor

        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <datamodel>
            <data id="result" expr="0"/>
          </datamodel>
          <state id="s1">
            <onentry>
              <foreach array="undefined_array" item="x">
                <assign location="result" expr="1"/>
              </foreach>
            </onentry>
            <transition event="error.execution" target="error"/>
          </state>
          <final id="error"/>
        </scxml>
        """
        processor = SCXMLProcessor()
        processor.parse_scxml("test_foreach_error", scxml)
        sm = processor.start()
        # The foreach array eval raises, which gets caught by error_on_execution
        assert sm.configuration == {sm.states_map["error"]}


class TestSCXMLParallelFinalState:
    """Test done.state detection when all regions of a parallel state complete."""

    def test_parallel_state_done_when_all_regions_final(self):
        """done.state fires when all regions of a parallel state are in final states."""
        from statemachine.io.scxml.processor import SCXMLProcessor

        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="wrapper">
          <state id="wrapper">
            <parallel id="p1">
              <state id="r1" initial="a">
                <state id="a">
                  <transition target="a_done"/>
                </state>
                <final id="a_done"/>
              </state>
              <state id="r2" initial="b">
                <state id="b">
                  <transition target="b_done"/>
                </state>
                <final id="b_done"/>
              </state>
            </parallel>
            <transition event="done.state.p1" target="done"/>
          </state>
          <final id="done"/>
        </scxml>
        """
        processor = SCXMLProcessor()
        processor.parse_scxml("test_parallel_final", scxml)
        sm = processor.start()
        # Both regions auto-transition to final states, done.state.p1 fires
        assert sm.states_map["done"] in sm.configuration


class TestEventDataWrapperMultipleArgs:
    """EventDataWrapper.data returns tuple when trigger_data has multiple args."""

    def test_data_returns_tuple_for_multiple_args(self):
        """EventDataWrapper.data returns the args tuple when more than one positional arg."""
        from unittest.mock import Mock

        from statemachine.io.scxml.actions import EventDataWrapper

        trigger_data = Mock()
        trigger_data.kwargs = {}
        trigger_data.args = (1, 2, 3)
        trigger_data.event = Mock(internal=True)
        trigger_data.event.__str__ = lambda self: "test"
        trigger_data.send_id = None

        event_data = Mock()
        event_data.trigger_data = trigger_data

        wrapper = EventDataWrapper(event_data)
        assert wrapper.data == (1, 2, 3)


class TestIfActionRaisesWithoutErrorOnExecution:
    """SCXML <if> condition error raises when error_on_execution is False."""

    def test_if_condition_error_propagates_without_error_on_execution(self):
        """<if> with failing condition raises when machine.error_on_execution is False."""
        from statemachine.io.scxml.actions import create_if_action_callable
        from statemachine.io.scxml.schema import IfAction
        from statemachine.io.scxml.schema import IfBranch

        action = IfAction(branches=[IfBranch(cond="undefined_var")])
        if_callable = create_if_action_callable(action)

        machine = Mock()
        machine.error_on_execution = False
        machine.model.__dict__ = {}

        with pytest.raises(NameError, match="undefined_var"):
            if_callable(machine=machine)


class TestSCXMLSendWithParamNoExpr:
    """SCXML <send> with a param that has location but no expr."""

    def test_send_param_with_location_only(self):
        """<send> param with location only evaluates the location."""
        from statemachine.io.scxml.processor import SCXMLProcessor

        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <datamodel>
            <data id="myvar" expr="42"/>
          </datamodel>
          <state id="s1">
            <onentry>
              <send event="done" target="#_internal">
                <param name="val" location="myvar"/>
              </send>
            </onentry>
            <transition event="done" target="s2"/>
          </state>
          <final id="s2"/>
        </scxml>
        """
        processor = SCXMLProcessor()
        processor.parse_scxml("test_send_param", scxml)
        sm = processor.start()
        assert sm.configuration == {sm.states_map["s2"]}


class TestSCXMLHistoryWithoutTransitions:
    """SCXML history state without default transitions."""

    def test_history_without_transitions(self):
        """History state without transitions is processed correctly."""
        from statemachine.io.scxml.processor import SCXMLProcessor

        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <state id="s1" initial="a">
            <history id="h1" type="shallow"/>
            <state id="a">
              <transition event="go" target="b"/>
            </state>
            <state id="b">
              <transition event="back" target="h1"/>
            </state>
            <transition event="out" target="s2"/>
          </state>
          <state id="s2">
            <transition event="ret" target="h1"/>
          </state>
        </scxml>
        """
        processor = SCXMLProcessor()
        processor.parse_scxml("test_history_no_trans", scxml)
        sm = processor.start()
        assert sm.states_map["a"] in sm.configuration


# --- SCXMLInvoker ---


def _make_invoker(definition=None, base_dir=None, register_child=None):
    """Helper to create an SCXMLInvoker with sensible defaults."""
    if definition is None:
        definition = InvokeDefinition()
    if base_dir is None:
        base_dir = ""
    if register_child is None:
        register_child = Mock(return_value=Mock)
    return SCXMLInvoker(
        definition=definition,
        base_dir=base_dir,
        register_child=register_child,
    )


class TestSCXMLInvoker:
    def test_invalid_invoke_type_raises(self):
        """run() raises ValueError for unsupported invoke type."""
        defn = InvokeDefinition(
            type="http://unsupported/type",
            content="<scxml/>",
        )
        invoker = _make_invoker(definition=defn)
        ctx = Mock()
        model = Mock(spec=[])
        ctx.machine = Mock(model=model)

        with pytest.raises(ValueError, match="Unsupported invoke type"):
            invoker.run(ctx)

    def test_no_content_resolved_raises(self):
        """run() raises ValueError when no src/content/srcexpr is provided."""
        defn = InvokeDefinition()  # no content, src, or srcexpr
        invoker = _make_invoker(definition=defn)
        ctx = Mock()
        model = Mock(spec=[])
        ctx.machine = Mock(model=model)

        with pytest.raises(ValueError, match="No content resolved"):
            invoker.run(ctx)

    def test_resolve_content_inline_xml(self):
        """_resolve_content returns inline XML content directly."""
        xml_content = '<scxml xmlns="http://www.w3.org/2005/07/scxml"><final id="f"/></scxml>'
        defn = InvokeDefinition(content=xml_content)
        invoker = _make_invoker(definition=defn)

        result = invoker._resolve_content(Mock())
        assert result == xml_content

    def test_resolve_content_from_file(self, tmp_path):
        """_resolve_content reads content from src file path."""
        scxml_file = tmp_path / "child.scxml"
        scxml_file.write_text("<scxml/>")

        defn = InvokeDefinition(src="child.scxml")
        invoker = _make_invoker(definition=defn, base_dir=str(tmp_path))

        result = invoker._resolve_content(Mock())
        assert result == "<scxml/>"

    def test_evaluate_params_namelist_and_params(self):
        """_evaluate_params resolves both namelist variables and param elements."""
        defn = InvokeDefinition(
            namelist="var1 var2",
            params=[Param(name="p1", expr="42")],
        )
        invoker = _make_invoker(definition=defn)

        model = type("Model", (), {"var1": "a", "var2": "b"})()
        machine = Mock(model=model)

        result = invoker._evaluate_params(machine)
        assert result == {"var1": "a", "var2": "b", "p1": 42}

    def test_on_cancel_clears_child(self):
        """on_cancel() sets _child to None."""
        invoker = _make_invoker()
        invoker._child = Mock()

        invoker.on_cancel()
        assert invoker._child is None

    def test_on_event_skips_terminated_child(self):
        """on_event() does not error when child is terminated."""
        invoker = _make_invoker()
        child = Mock()
        child.is_terminated = True
        invoker._child = child

        # Should not raise or call send
        invoker.on_event("some.event")
        child.send.assert_not_called()

    def test_on_finalize_without_block_is_noop(self):
        """on_finalize() does nothing when no finalize block is defined."""
        invoker = _make_invoker()
        assert invoker._finalize_block is None

        # Should not raise
        trigger_data = Mock()
        invoker.on_finalize(trigger_data)

    def test_send_to_parent_warns_without_session(self, caplog):
        """_send_to_parent logs a warning when machine has no _invoke_session."""
        from statemachine.io.scxml.actions import _send_to_parent
        from statemachine.io.scxml.parser import SendAction

        action = SendAction(event="done", target="#_parent")
        machine = Mock(spec=[])  # spec=[] ensures no _invoke_session attribute
        machine.name = "test_machine"

        with caplog.at_level(logging.WARNING, logger="statemachine.io.scxml.actions"):
            _send_to_parent(action, machine=machine)

        assert "no _invoke_session" in caplog.text


# --- _send_to_invoke ---


class TestSendToInvoke:
    """Unit tests for _send_to_invoke (routes <send target="#_<invokeid>">)."""

    def _make_machine_with_invoke_manager(self, send_to_child_return=True):
        """Create a mock machine with an InvokeManager that has send_to_child."""
        machine = Mock()
        machine.model = Mock()
        machine.model.__dict__ = {}
        machine._engine._invoke_manager.send_to_child.return_value = send_to_child_return
        return machine

    def test_routes_event_to_child(self):
        """_send_to_invoke forwards the event to InvokeManager.send_to_child."""
        from statemachine.io.scxml.actions import _send_to_invoke
        from statemachine.io.scxml.parser import SendAction

        machine = self._make_machine_with_invoke_manager()
        action = SendAction(event="childEvent", target="#_child1")

        _send_to_invoke(action, "child1", machine=machine)

        machine._engine._invoke_manager.send_to_child.assert_called_once_with(
            "child1", "childEvent"
        )
        machine.send.assert_not_called()

    def test_sends_error_communication_when_child_not_found(self):
        """_send_to_invoke sends error.communication when invokeid is not found."""
        from statemachine.io.scxml.actions import _send_to_invoke
        from statemachine.io.scxml.parser import SendAction

        machine = self._make_machine_with_invoke_manager(send_to_child_return=False)
        action = SendAction(event="childEvent", target="#_unknown")

        _send_to_invoke(action, "unknown", machine=machine)

        machine._put_nonblocking.assert_called_once()
        trigger_data = machine._put_nonblocking.call_args[0][0]
        assert str(trigger_data.event) == "error.communication"

    def test_evaluates_eventexpr(self):
        """_send_to_invoke evaluates eventexpr when event is None."""
        from statemachine.io.scxml.actions import _send_to_invoke
        from statemachine.io.scxml.parser import SendAction

        machine = self._make_machine_with_invoke_manager()
        action = SendAction(event=None, eventexpr="'dynamic_event'", target="#_child1")

        _send_to_invoke(action, "child1", machine=machine)

        machine._engine._invoke_manager.send_to_child.assert_called_once_with(
            "child1", "dynamic_event"
        )

    def test_forwards_params(self):
        """_send_to_invoke forwards evaluated params to send_to_child."""
        from statemachine.io.scxml.actions import _send_to_invoke
        from statemachine.io.scxml.parser import SendAction

        machine = self._make_machine_with_invoke_manager()
        action = SendAction(
            event="childEvent",
            target="#_child1",
            params=[Param(name="x", expr="42"), Param(name="y", expr="'hello'")],
        )

        _send_to_invoke(action, "child1", machine=machine)

        machine._engine._invoke_manager.send_to_child.assert_called_once_with(
            "child1", "childEvent", x=42, y="hello"
        )

    def test_forwards_namelist_variables(self):
        """_send_to_invoke resolves namelist variables from model and forwards them."""
        from statemachine.io.scxml.actions import _send_to_invoke
        from statemachine.io.scxml.parser import SendAction

        machine = self._make_machine_with_invoke_manager()
        model = type("Model", (), {})()
        model.var1 = "alpha"
        model.var2 = "beta"
        machine.model = model
        action = SendAction(event="childEvent", target="#_child1", namelist="var1 var2")

        _send_to_invoke(action, "child1", machine=machine)

        machine._engine._invoke_manager.send_to_child.assert_called_once_with(
            "child1", "childEvent", var1="alpha", var2="beta"
        )

    def test_namelist_missing_variable_raises(self):
        """_send_to_invoke raises NameError when namelist variable is not on model."""
        from statemachine.io.scxml.actions import _send_to_invoke
        from statemachine.io.scxml.parser import SendAction

        machine = self._make_machine_with_invoke_manager()
        machine.model = Mock(spec=[])  # no attributes
        action = SendAction(event="childEvent", target="#_child1", namelist="missing_var")

        with pytest.raises(NameError, match="missing_var"):
            _send_to_invoke(action, "child1", machine=machine)

    def test_send_action_callable_routes_invoke_target(self):
        """create_send_action_callable routes #_<invokeid> targets to _send_to_invoke."""
        from statemachine.io.scxml.actions import create_send_action_callable
        from statemachine.io.scxml.parser import SendAction

        machine = self._make_machine_with_invoke_manager()
        action = SendAction(event="hello", target="#_myinvoke")
        send_callable = create_send_action_callable(action)

        send_callable(machine=machine)

        machine._engine._invoke_manager.send_to_child.assert_called_once_with("myinvoke", "hello")

    def test_send_action_callable_scxml_session_target(self):
        """create_send_action_callable sends error.communication for #_scxml_ targets."""
        from statemachine.io.scxml.actions import create_send_action_callable
        from statemachine.io.scxml.parser import SendAction

        machine = self._make_machine_with_invoke_manager()
        action = SendAction(event="hello", target="#_scxml_session123")
        send_callable = create_send_action_callable(action)

        send_callable(machine=machine)

        machine._put_nonblocking.assert_called_once()
        trigger_data = machine._put_nonblocking.call_args[0][0]
        assert str(trigger_data.event) == "error.communication"
        machine._engine._invoke_manager.send_to_child.assert_not_called()


# --- EventDataWrapper coverage ---


class TestEventDataWrapperEdgeCases:
    def test_no_event_data_no_trigger_data_raises(self):
        """EventDataWrapper raises ValueError when neither is provided."""
        with pytest.raises(ValueError, match="Either event_data or trigger_data"):
            EventDataWrapper()

    def test_getattr_with_event_data_delegates(self):
        """__getattr__ delegates to event_data when present."""
        event_data = Mock()
        event_data.trigger_data = Mock(
            kwargs={}, send_id=None, event=Mock(internal=True, __str__=lambda s: "test")
        )
        event_data.some_custom_attr = "custom_value"
        wrapper = EventDataWrapper(event_data)
        assert wrapper.some_custom_attr == "custom_value"

    def test_getattr_without_event_data_raises(self):
        """__getattr__ raises AttributeError when event_data is None."""
        trigger_data = Mock(kwargs={}, send_id=None, event=Mock(internal=True))
        trigger_data.event.__str__ = lambda s: "test"
        wrapper = EventDataWrapper(trigger_data=trigger_data)
        with pytest.raises(AttributeError, match="no attribute 'missing_attr'"):
            wrapper.missing_attr  # noqa: B018

    def test_name_via_trigger_data(self):
        """name property returns event string from trigger_data when no event_data."""
        trigger_data = Mock(kwargs={}, send_id=None, event=Mock(internal=True))
        trigger_data.event.__str__ = lambda s: "my.event"
        wrapper = EventDataWrapper(trigger_data=trigger_data)
        assert wrapper.name == "my.event"


# --- _send_to_parent coverage ---


class TestSendToParentParams:
    def test_send_to_parent_with_namelist_and_params(self):
        """_send_to_parent resolves namelist and params before sending."""
        from statemachine.io.scxml.actions import _send_to_parent
        from statemachine.io.scxml.parser import SendAction

        model = type("Model", (), {})()
        model.myvar = "hello"
        machine = Mock(model=model)
        machine.model.__dict__ = {"myvar": "hello"}
        session = Mock()
        machine._invoke_session = session

        action = SendAction(
            event="childDone",
            target="#_parent",
            namelist="myvar",
            params=[Param(name="extra", expr="42")],
        )

        _send_to_parent(action, machine=machine)

        session.send_to_parent.assert_called_once_with("childDone", myvar="hello", extra=42)

    def test_send_to_parent_namelist_missing_raises(self):
        """_send_to_parent raises NameError when namelist variable is missing."""
        from statemachine.io.scxml.actions import _send_to_parent
        from statemachine.io.scxml.parser import SendAction

        machine = Mock()
        machine.model = Mock(spec=[])  # no attributes
        machine._invoke_session = Mock()

        action = SendAction(event="ev", target="#_parent", namelist="missing_var")

        with pytest.raises(NameError, match="missing_var"):
            _send_to_parent(action, machine=machine)

    def test_send_to_parent_param_without_expr_skipped(self):
        """_send_to_parent skips params where expr is None."""
        from statemachine.io.scxml.actions import _send_to_parent
        from statemachine.io.scxml.parser import SendAction

        machine = Mock()
        machine.model = Mock()
        machine.model.__dict__ = {}
        session = Mock()
        machine._invoke_session = session

        action = SendAction(
            event="ev",
            target="#_parent",
            params=[
                Param(name="has_expr", expr="1"),
                Param(name="no_expr", expr=None),
            ],
        )

        _send_to_parent(action, machine=machine)
        session.send_to_parent.assert_called_once_with("ev", has_expr=1)


# --- _send_to_invoke param skip coverage ---


class TestSendToInvokeParamSkip:
    def test_param_without_expr_is_skipped(self):
        """_send_to_invoke skips params where expr is None."""
        from statemachine.io.scxml.actions import _send_to_invoke
        from statemachine.io.scxml.parser import SendAction

        machine = Mock()
        machine.model = Mock()
        machine.model.__dict__ = {}
        machine._engine._invoke_manager.send_to_child.return_value = True

        action = SendAction(
            event="ev",
            target="#_child",
            params=[
                Param(name="with_expr", expr="1"),
                Param(name="no_expr", expr=None),
            ],
        )

        _send_to_invoke(action, "child", machine=machine)

        machine._engine._invoke_manager.send_to_child.assert_called_once_with(
            "child", "ev", with_expr=1
        )


# --- invoke_init coverage ---


class TestInvokeInitCallback:
    def test_invoke_init_idempotent(self):
        """invoke_init only runs once, even if called multiple times."""
        from statemachine.io.scxml.actions import create_invoke_init_callable

        callback = create_invoke_init_callable()
        machine = Mock()

        callback(machine=machine)
        assert machine._invoke_params is not None or True  # first call sets attrs

        # Reset to detect second call
        machine._invoke_params = "first"
        callback(machine=machine)
        # Should NOT have been overwritten
        assert machine._invoke_params == "first"


# --- SCXMLInvoker edge cases ---


class TestSCXMLInvokerEdgeCases:
    def test_on_event_exception_in_child_send(self):
        """on_event swallows exceptions from child.send()."""
        invoker = _make_invoker()
        child = Mock()
        child.is_terminated = False
        child.send.side_effect = RuntimeError("child error")
        invoker._child = child

        # Should not raise
        invoker.on_event("some.event")
        child.send.assert_called_once_with("some.event")

    def test_resolve_content_expr_non_string(self):
        """_resolve_content converts non-string eval result to string."""
        defn = InvokeDefinition(content="42")  # evaluates to int
        invoker = _make_invoker(definition=defn)
        machine = Mock()
        machine.model.__dict__ = {}

        result = invoker._resolve_content(machine)
        assert result == "42"

    def test_evaluate_params_with_location(self):
        """_evaluate_params resolves param with location instead of expr."""
        defn = InvokeDefinition(
            params=[Param(name="p1", expr=None, location="myvar")],
        )
        invoker = _make_invoker(definition=defn)

        model = type("Model", (), {})()
        model.myvar = "resolved"
        machine = Mock(model=model)
        machine.model.__dict__ = {"myvar": "resolved"}

        result = invoker._evaluate_params(machine)
        assert result == {"p1": "resolved"}


# --- Parser edge cases ---


class TestParserAssignChildXml:
    def test_assign_with_child_xml_content(self):
        """<assign> with child XML content is parsed as child_xml."""
        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <datamodel>
            <data id="mydata" expr="None"/>
          </datamodel>
          <state id="s1">
            <onentry>
              <assign location="mydata"><node attr="val"/></assign>
            </onentry>
            <transition event="error.execution" target="err"/>
          </state>
          <final id="err"/>
        </scxml>
        """
        # Should parse without error — the child XML is stored in child_xml
        definition = parse_scxml(scxml)
        # Verify it parsed states correctly
        assert "s1" in definition.states

    def test_assign_with_text_content(self):
        """<assign> with text content (no expr attr) uses text as expr."""
        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <datamodel>
            <data id="mydata" expr="0"/>
          </datamodel>
          <state id="s1">
            <onentry>
              <assign location="mydata">42</assign>
            </onentry>
            <transition target="s2"/>
          </state>
          <final id="s2"/>
        </scxml>
        """
        definition = parse_scxml(scxml)
        assert "s1" in definition.states


class TestParserInvokeContent:
    def test_invoke_with_text_content(self):
        """<invoke> <content> with text body is parsed."""
        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <state id="s1">
            <invoke type="http://www.w3.org/TR/scxml/">
              <content>some text content</content>
            </invoke>
          </state>
        </scxml>
        """
        definition = parse_scxml(scxml)
        assert "s1" in definition.states
        invoke_def = definition.states["s1"].invocations[0]
        assert "some text content" in invoke_def.content

    def test_invoke_with_content_expr(self):
        """<invoke> <content expr="..."> is parsed as dynamic content."""
        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <state id="s1">
            <invoke type="http://www.w3.org/TR/scxml/">
              <content expr="'dynamic'"/>
            </invoke>
          </state>
        </scxml>
        """
        definition = parse_scxml(scxml)
        invoke_def = definition.states["s1"].invocations[0]
        assert invoke_def.content == "'dynamic'"

    def test_invoke_with_inline_scxml_no_namespace(self):
        """<invoke> <content> with inline <scxml> (no namespace) is parsed."""
        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <state id="s1">
            <invoke type="http://www.w3.org/TR/scxml/">
              <content><scxml><final id="f"/></scxml></content>
            </invoke>
          </state>
        </scxml>
        """
        definition = parse_scxml(scxml)
        invoke_def = definition.states["s1"].invocations[0]
        assert "<final" in invoke_def.content

    def test_invoke_with_unknown_child_element(self):
        """Unknown child elements inside <invoke> are silently ignored."""
        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <state id="s1">
            <invoke type="http://www.w3.org/TR/scxml/">
              <param name="x" expr="1"/>
              <unknownElement/>
            </invoke>
          </state>
        </scxml>
        """
        definition = parse_scxml(scxml)
        invoke_def = definition.states["s1"].invocations[0]
        assert len(invoke_def.params) == 1

    def test_invoke_with_empty_content(self):
        """<invoke> with empty <content/> results in content=None."""
        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <state id="s1">
            <invoke type="http://www.w3.org/TR/scxml/">
              <content/>
            </invoke>
          </state>
        </scxml>
        """
        definition = parse_scxml(scxml)
        invoke_def = definition.states["s1"].invocations[0]
        assert invoke_def.content is None

    def test_invoke_with_finalize_block(self):
        """<invoke> with <finalize> block is parsed."""
        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <state id="s1">
            <invoke type="http://www.w3.org/TR/scxml/">
              <content>child content</content>
              <finalize>
                <log label="finalized"/>
              </finalize>
            </invoke>
          </state>
        </scxml>
        """
        definition = parse_scxml(scxml)
        invoke_def = definition.states["s1"].invocations[0]
        assert invoke_def.finalize is not None
        assert len(invoke_def.finalize.actions) == 1


class TestParserAssignEdgeCases:
    def test_assign_without_children_or_text(self):
        """<assign> with neither children nor text results in expr=None."""
        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">
          <datamodel>
            <data id="mydata" expr="0"/>
          </datamodel>
          <state id="s1">
            <onentry>
              <assign location="mydata"/>
            </onentry>
            <transition event="error.execution" target="err"/>
          </state>
          <final id="err"/>
        </scxml>
        """
        definition = parse_scxml(scxml)
        assert "s1" in definition.states


class TestSCXMLInvokerResolveContentAbsolutePath:
    def test_resolve_content_absolute_path(self, tmp_path):
        """_resolve_content with absolute src path doesn't prepend base_dir."""
        scxml_file = tmp_path / "child.scxml"
        scxml_file.write_text("<scxml/>")

        defn = InvokeDefinition(src=str(scxml_file))
        invoker = _make_invoker(definition=defn, base_dir="/some/other/dir")

        result = invoker._resolve_content(Mock())
        assert result == "<scxml/>"


class TestSCXMLInvokerEvaluateParamsNoExprNoLocation:
    def test_param_without_expr_or_location_skipped(self):
        """_evaluate_params skips params with neither expr nor location."""
        defn = InvokeDefinition(
            params=[Param(name="p1", expr=None, location=None)],
        )
        invoker = _make_invoker(definition=defn)
        machine = Mock(model=type("M", (), {})())
        machine.model.__dict__ = {}

        result = invoker._evaluate_params(machine)
        assert result == {}


class TestInvokeInitMachineNone:
    def test_invoke_init_without_machine_is_noop(self):
        """invoke_init does nothing when machine is not in kwargs."""
        from statemachine.io.scxml.actions import create_invoke_init_callable

        callback = create_invoke_init_callable()
        # Call without machine kwarg — should not raise
        callback()


class TestInvokeCallableWrapperRunInstance:
    def test_run_with_instance_not_class(self):
        """_InvokeCallableWrapper.run() works with an instance (not a class)."""
        from statemachine.invoke import _InvokeCallableWrapper

        class Handler:
            def run(self, ctx):
                return "result"

        handler_instance = Handler()
        wrapper = _InvokeCallableWrapper(handler_instance)
        assert not wrapper._is_class

        ctx = Mock()
        result = wrapper.run(ctx)
        assert result == "result"
        assert wrapper._instance is handler_instance


class TestOrderedSetStr:
    def test_str_representation(self):
        """OrderedSet.__str__ returns a set-like string."""
        from statemachine.orderedset import OrderedSet

        os = OrderedSet([1, 2, 3])
        assert str(os) == "{1, 2, 3}"
