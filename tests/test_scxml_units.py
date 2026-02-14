"""Unit tests for SCXML parser, actions, and schema modules."""

import xml.etree.ElementTree as ET
from unittest.mock import Mock

import pytest
from statemachine.io.scxml.actions import Log
from statemachine.io.scxml.actions import ParseTime
from statemachine.io.scxml.actions import create_action_callable
from statemachine.io.scxml.actions import create_datamodel_action_callable
from statemachine.io.scxml.parser import parse_element
from statemachine.io.scxml.parser import parse_scxml
from statemachine.io.scxml.parser import strip_namespaces
from statemachine.io.scxml.schema import CancelAction
from statemachine.io.scxml.schema import DataModel
from statemachine.io.scxml.schema import IfBranch
from statemachine.io.scxml.schema import LogAction

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
    def test_state_without_id_raises(self):
        """State element without id attribute raises ValueError."""
        xml = '<scxml xmlns="http://www.w3.org/2005/07/scxml"><state/></scxml>'
        with pytest.raises(ValueError, match="State must have an 'id' attribute"):
            parse_scxml(xml)


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
